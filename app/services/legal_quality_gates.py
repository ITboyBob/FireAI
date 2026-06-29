from dataclasses import dataclass, field, fields
from enum import Enum
from hashlib import sha256
from typing import Literal
import re

from app.services.legal_extractor import ExtractionResult
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    SourceRef,
)
from app.services.legal_intermediate import LegalDocumentIntermediate
from app.services.structure_parser import ParsedDocument


class GateOutcome(str, Enum):
    PASS = "pass"
    REVIEW_REQUIRED = "review_required"
    FAIL = "fail"


@dataclass(frozen=True, slots=True, kw_only=True)
class GateResult:
    gate_id: str
    outcome: GateOutcome
    measured: dict[str, object] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    reason_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityInput:
    source_sha256: str
    document_id: str
    extraction_class: ExtractionClass
    content_class: ContentClass
    source: SourceRef
    extraction: ExtractionResult
    intermediate: LegalDocumentIntermediate
    parsed: ParsedDocument
    chunks: tuple[dict, ...]

    def replace(self, **kwargs) -> "QualityInput":
        data = {field.name: getattr(self, field.name) for field in fields(self)}
        data.update(kwargs)
        return self.__class__(**data)


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityReport:
    ruleset_version: str
    source_sha256: str
    document_id: str
    gates: tuple[GateResult, ...]
    overall: GateOutcome
    measured: dict[str, object] = field(default_factory=dict)


RULESET_VERSION = "legal-quality-v1"

ARTICLE_PATTERN = re.compile(
    r"^第([一二三四五六七八九十百千万零〇两0-9]+)条(?:\s|　|$)(.*)$",
    re.DOTALL,
)
PAGE_FIELD_PATTERN = re.compile(r"PAGE\s*\\\*\s*MERGEFORMAT|NUMPAGES|HYPERLINK")
PAGE_LINE_PATTERN = re.compile(r"^第?\s*\d+\s*页$")
PRINT_RECORD_PATTERN = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*印发[。.]?$"
)
COPY_DISTRIBUTION_PATTERN = re.compile(r"^抄送\s*[：:]")
ADMIN_OFFICE_FOOTER_PATTERN = re.compile(
    r"^[^，,；;：:]{2,40}(?:办公室|办公厅)[。.]?$"
)
LOCAL_GOVERNMENT_REGULATION_FOOTER_PATTERN = re.compile(
    r"^(?!本(?:规定|办法|细则|条例))[一-鿿]{1,16}"
    r"(?:省|市|自治区|自治州|县)人民政府规章[。.]?$"
)


def evaluate_legal_quality(quality_input: QualityInput) -> QualityReport:
    gates: list[GateResult] = []
    gates.append(_gate_source_identity(quality_input))
    gates.append(_gate_document_identity(quality_input))

    if any(g.outcome is GateOutcome.FAIL for g in gates):
        return _build_report(quality_input, gates)

    gates.append(_gate_boundary_confirmed(quality_input))
    if gates[-1].outcome in (GateOutcome.FAIL, GateOutcome.REVIEW_REQUIRED):
        return _build_report(quality_input, gates)

    gates.append(_gate_article_start(quality_input))
    if gates[-1].outcome is GateOutcome.FAIL:
        return _build_report(quality_input, gates)

    gates.append(_gate_article_numbers(quality_input))
    gates.append(_gate_article_non_empty(quality_input))
    gates.append(_gate_body_purity(quality_input))
    gates.append(_gate_exclusion_isolation(quality_input))
    gates.append(_gate_cross_layer_consistency(quality_input))
    gates.append(_gate_chunk_coverage(quality_input))

    return _build_report(quality_input, gates)


def _build_report(quality_input: QualityInput, gates: list[GateResult]) -> QualityReport:
    overall = GateOutcome.PASS
    for gate in gates:
        if gate.outcome is GateOutcome.FAIL:
            overall = GateOutcome.FAIL
            break
        if gate.outcome is GateOutcome.REVIEW_REQUIRED and overall is not GateOutcome.FAIL:
            overall = GateOutcome.REVIEW_REQUIRED

    return QualityReport(
        ruleset_version=RULESET_VERSION,
        source_sha256=quality_input.source_sha256,
        document_id=quality_input.document_id,
        gates=tuple(gates),
        overall=overall,
    )


def _gate_source_identity(quality_input: QualityInput) -> GateResult:
    digests = {
        quality_input.source_sha256,
        quality_input.source.source_sha256,
        quality_input.extraction.source_sha256,
        quality_input.intermediate.source_ref.source_sha256,
    }
    if quality_input.parsed.source_sha256 is not None:
        digests.add(quality_input.parsed.source_sha256)
    for chunk in quality_input.chunks:
        if "source_sha256" in chunk:
            digests.add(chunk["source_sha256"])

    if len(digests) != 1:
        return GateResult(
            gate_id="source_identity",
            outcome=GateOutcome.FAIL,
            measured={"digest_count": len(digests)},
            evidence_refs=tuple(f"digest:{digest}" for digest in sorted(digests)),
            reason_code="source_digest_mismatch",
        )

    try:
        current_digest = sha256(
            quality_input.source.source_path.read_bytes()
        ).hexdigest()
    except OSError as exc:
        return GateResult(
            gate_id="source_identity",
            outcome=GateOutcome.FAIL,
            measured={},
            evidence_refs=(),
            reason_code=f"source_read_error:{exc.__class__.__name__}",
        )

    if current_digest != quality_input.source_sha256:
        return GateResult(
            gate_id="source_identity",
            outcome=GateOutcome.FAIL,
            measured={"expected": quality_input.source_sha256, "actual": current_digest},
            evidence_refs=("source_path",),
            reason_code="source_digest_changed",
        )

    return GateResult(
        gate_id="source_identity",
        outcome=GateOutcome.PASS,
        measured={"source_sha256": quality_input.source_sha256},
        evidence_refs=(str(quality_input.source.source_path),),
    )


def _gate_document_identity(quality_input: QualityInput) -> GateResult:
    document_ids = {
        quality_input.document_id,
        quality_input.intermediate.document_id,
        quality_input.parsed.document_id,
    }
    for chunk in quality_input.chunks:
        if "document_id" in chunk:
            document_ids.add(chunk["document_id"])

    if len(document_ids) != 1:
        return GateResult(
            gate_id="document_identity",
            outcome=GateOutcome.FAIL,
            measured={"document_id_count": len(document_ids)},
            evidence_refs=tuple(f"document_id:{doc_id}" for doc_id in sorted(document_ids)),
            reason_code="document_id_mismatch",
        )

    return GateResult(
        gate_id="document_identity",
        outcome=GateOutcome.PASS,
        measured={"document_id": quality_input.document_id},
        evidence_refs=(),
    )


def _gate_boundary_confirmed(quality_input: QualityInput) -> GateResult:
    if quality_input.intermediate.boundary.status != "confirmed":
        return GateResult(
            gate_id="boundary_confirmed",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"boundary_status": quality_input.intermediate.boundary.status},
            evidence_refs=tuple(quality_input.intermediate.boundary.ambiguities),
            reason_code="boundary_not_confirmed",
        )
    if quality_input.intermediate.extraction_report.status != "confirmed":
        return GateResult(
            gate_id="boundary_confirmed",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"report_status": quality_input.intermediate.extraction_report.status},
            evidence_refs=(),
            reason_code="extraction_report_not_confirmed",
        )
    return GateResult(
        gate_id="boundary_confirmed",
        outcome=GateOutcome.PASS,
        measured={"boundary_status": "confirmed"},
        evidence_refs=(
            f"start_block:{quality_input.intermediate.boundary.start.block_order}",
            f"end_block:{quality_input.intermediate.boundary.end.block_order}",
        ),
    )


def _gate_article_start(quality_input: QualityInput) -> GateResult:
    title_units = [
        unit for unit in quality_input.intermediate.body_units if unit.kind == "title"
    ]
    article_units = [
        unit for unit in quality_input.intermediate.body_units if unit.kind == "article"
    ]

    if len(title_units) != 1:
        return GateResult(
            gate_id="article_start",
            outcome=GateOutcome.FAIL,
            measured={"title_count": len(title_units)},
            evidence_refs=(),
            reason_code="title_not_unique",
        )

    if not article_units:
        return GateResult(
            gate_id="article_start",
            outcome=GateOutcome.FAIL,
            measured={"article_count": 0},
            evidence_refs=(),
            reason_code="no_articles",
        )

    first_article = article_units[0]
    match = ARTICLE_PATTERN.match(first_article.text)
    if match is None or _article_number_value(match.group(1)) != 1:
        return GateResult(
            gate_id="article_start",
            outcome=GateOutcome.FAIL,
            measured={"first_article_text": first_article.text},
            evidence_refs=(first_article.unit_id,),
            reason_code="first_article_not_article_one",
        )

    return GateResult(
        gate_id="article_start",
        outcome=GateOutcome.PASS,
        measured={
            "title": title_units[0].text,
            "first_article": first_article.text,
        },
        evidence_refs=(title_units[0].unit_id, first_article.unit_id),
    )


def _gate_article_numbers(quality_input: QualityInput) -> GateResult:
    article_units = [
        unit for unit in quality_input.intermediate.body_units if unit.kind == "article"
    ]
    numbers: list[int] = []
    raw_nos: list[str] = []
    for unit in article_units:
        match = ARTICLE_PATTERN.match(unit.text)
        if match is None:
            return GateResult(
                gate_id="article_numbers",
                outcome=GateOutcome.FAIL,
                measured={"invalid_article": unit.text},
                evidence_refs=(unit.unit_id,),
                reason_code="article_missing_number",
            )
        numbers.append(_article_number_value(match.group(1)))
        raw_nos.append(match.group(1))

    if len(numbers) != len(set(numbers)):
        duplicates = {n for n in numbers if numbers.count(n) > 1}
        return GateResult(
            gate_id="article_numbers",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"duplicate_numbers": sorted(duplicates)},
            evidence_refs=(),
            reason_code="duplicate_article_numbers",
        )

    if numbers and numbers != list(range(1, len(numbers) + 1)):
        return GateResult(
            gate_id="article_numbers",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={
                "expected_sequence": list(range(1, len(numbers) + 1)),
                "actual_numbers": numbers,
            },
            evidence_refs=(),
            reason_code="article_sequence_broken",
        )

    return GateResult(
        gate_id="article_numbers",
        outcome=GateOutcome.PASS,
        measured={"article_count": len(numbers)},
        evidence_refs=tuple(raw_nos),
    )


def _gate_article_non_empty(quality_input: QualityInput) -> GateResult:
    article_units = [
        unit for unit in quality_input.intermediate.body_units if unit.kind == "article"
    ]
    empty_units: list[str] = []
    for unit in article_units:
        body = unit.text
        match = ARTICLE_PATTERN.match(body)
        if match is not None:
            body = match.group(2).strip()
        if not body:
            empty_units.append(unit.unit_id)

    if empty_units:
        return GateResult(
            gate_id="article_non_empty",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"empty_article_units": empty_units},
            evidence_refs=tuple(empty_units),
            reason_code="empty_articles",
        )

    return GateResult(
        gate_id="article_non_empty",
        outcome=GateOutcome.PASS,
        measured={"article_count": len(article_units)},
        evidence_refs=(),
    )


def _gate_body_purity(quality_input: QualityInput) -> GateResult:
    if quality_input.extraction_class is not ExtractionClass.W:
        return GateResult(
            gate_id="body_purity",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_W_extraction"},
            evidence_refs=(),
        )

    contaminants: list[dict[str, str]] = []
    for unit in quality_input.intermediate.body_units:
        if unit.kind not in {"title", "article", "paragraph"}:
            continue
        text = unit.text
        if PAGE_FIELD_PATTERN.search(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "page_field"})
        elif PAGE_LINE_PATTERN.fullmatch(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "page_line"})
        elif PRINT_RECORD_PATTERN.search(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "print_record"})
        elif COPY_DISTRIBUTION_PATTERN.match(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "copy_distribution"})
        elif ADMIN_OFFICE_FOOTER_PATTERN.fullmatch(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "admin_office_footer"})
        elif LOCAL_GOVERNMENT_REGULATION_FOOTER_PATTERN.fullmatch(text):
            contaminants.append({"unit_id": unit.unit_id, "kind": "local_government_footer"})

    if contaminants:
        return GateResult(
            gate_id="body_purity",
            outcome=GateOutcome.FAIL,
            measured={"contaminants": contaminants},
            evidence_refs=tuple(c["unit_id"] for c in contaminants),
            reason_code="body_contaminated",
        )

    return GateResult(
        gate_id="body_purity",
        outcome=GateOutcome.PASS,
        measured={"contaminant_count": 0},
        evidence_refs=(),
    )


def _gate_exclusion_isolation(quality_input: QualityInput) -> GateResult:
    excluded_ranges = quality_input.intermediate.extraction_report.excluded_ranges
    overlaps: list[str] = []
    for excluded in excluded_ranges:
        for unit in quality_input.intermediate.body_units:
            if _spans_overlap(excluded.source_span, unit.source_span):
                overlaps.append(f"{excluded.kind}:{unit.unit_id}")

    if overlaps:
        return GateResult(
            gate_id="exclusion_isolation",
            outcome=GateOutcome.FAIL,
            measured={"overlaps": overlaps},
            evidence_refs=tuple(overlaps),
            reason_code="exclusion_overlaps_body",
        )

    return GateResult(
        gate_id="exclusion_isolation",
        outcome=GateOutcome.PASS,
        measured={"excluded_range_count": len(excluded_ranges)},
        evidence_refs=(),
    )


def _gate_cross_layer_consistency(quality_input: QualityInput) -> GateResult:
    intermediate = quality_input.intermediate
    parsed = quality_input.parsed

    if parsed.title != intermediate.target.title:
        return GateResult(
            gate_id="cross_layer_consistency",
            outcome=GateOutcome.FAIL,
            measured={
                "intermediate_title": intermediate.target.title,
                "parsed_title": parsed.title,
            },
            evidence_refs=(),
            reason_code="title_mismatch",
        )

    if parsed.source_sha256 != intermediate.source_ref.source_sha256:
        return GateResult(
            gate_id="cross_layer_consistency",
            outcome=GateOutcome.FAIL,
            measured={},
            evidence_refs=(),
            reason_code="source_sha256_mismatch",
        )

    intermediate_articles = tuple(
        unit for unit in intermediate.body_units if unit.kind == "article"
    )

    if len(intermediate_articles) != len(parsed.articles):
        return GateResult(
            gate_id="cross_layer_consistency",
            outcome=GateOutcome.FAIL,
            measured={
                "intermediate_article_count": len(intermediate_articles),
                "parsed_article_count": len(parsed.articles),
            },
            evidence_refs=(),
            reason_code="article_count_mismatch",
        )

    for index, (unit, parsed_article) in enumerate(
        zip(intermediate_articles, parsed.articles), start=1
    ):
        match = ARTICLE_PATTERN.match(unit.text)
        if match is None:
            return GateResult(
                gate_id="cross_layer_consistency",
                outcome=GateOutcome.FAIL,
                measured={"invalid_article_text": unit.text, "index": index},
                evidence_refs=(unit.unit_id,),
                reason_code="invalid_intermediate_article",
            )

        intermediate_no = f"第{match.group(1)}条"
        intermediate_body = match.group(2).strip()

        # 结构层会把 article 后的 paragraph 子单元拼接到该条正文中，
        # 中间格式层做一致性校验时也必须包含这些子单元。
        for child in intermediate.body_units:
            if child.kind == "paragraph" and child.parent_unit_id == unit.unit_id:
                intermediate_body = (
                    f"{intermediate_body}\n{child.text.strip()}"
                    if intermediate_body
                    else child.text.strip()
                )

        if intermediate_no != parsed_article.article_no:
            return GateResult(
                gate_id="cross_layer_consistency",
                outcome=GateOutcome.FAIL,
                measured={
                    "index": index,
                    "intermediate_no": intermediate_no,
                    "parsed_no": parsed_article.article_no,
                },
                evidence_refs=(unit.unit_id,),
                reason_code="article_number_mismatch",
            )

        if intermediate_body != parsed_article.text:
            return GateResult(
                gate_id="cross_layer_consistency",
                outcome=GateOutcome.FAIL,
                measured={
                    "index": index,
                    "intermediate_body": intermediate_body,
                    "parsed_body": parsed_article.text,
                },
                evidence_refs=(unit.unit_id,),
                reason_code="article_body_mismatch",
            )

    return GateResult(
        gate_id="cross_layer_consistency",
        outcome=GateOutcome.PASS,
        measured={"article_count": len(parsed.articles)},
        evidence_refs=(),
    )


def _gate_chunk_coverage(quality_input: QualityInput) -> GateResult:
    parsed = quality_input.parsed
    chunks = quality_input.chunks

    if not parsed.articles:
        return GateResult(
            gate_id="chunk_coverage",
            outcome=GateOutcome.FAIL,
            measured={"article_count": 0},
            evidence_refs=(),
            reason_code="no_articles_to_cover",
        )

    expected_indexes = set(range(1, len(parsed.articles) + 1))
    covered_indexes: set[int] = set()
    out_of_range: list[int] = []

    for chunk in chunks:
        article_index = chunk.get("article_index")
        if article_index is None:
            continue
        idx = int(article_index)
        if idx not in expected_indexes:
            out_of_range.append(idx)
        else:
            covered_indexes.add(idx)

    if out_of_range:
        return GateResult(
            gate_id="chunk_coverage",
            outcome=GateOutcome.FAIL,
            measured={"out_of_range_article_indexes": out_of_range},
            evidence_refs=(),
            reason_code="chunks_out_of_range",
        )

    missing = expected_indexes - covered_indexes
    if missing:
        return GateResult(
            gate_id="chunk_coverage",
            outcome=GateOutcome.FAIL,
            measured={"missing_article_indexes": sorted(missing)},
            evidence_refs=(),
            reason_code="articles_missing_chunks",
        )

    return GateResult(
        gate_id="chunk_coverage",
        outcome=GateOutcome.PASS,
        measured={
            "article_count": len(parsed.articles),
            "chunk_count": len(chunks),
        },
        evidence_refs=(),
    )


def _article_number_value(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    current = 0
    for character in value:
        if character in digits:
            current = digits[character]
            continue
        unit = units[character]
        total += (current or 1) * unit
        current = 0
    return total + current


def _span_key(span):
    return (
        span.start.block_order,
        span.start_char_offset,
        span.end.block_order,
        span.end_char_offset,
    )


def _spans_overlap(first, second) -> bool:
    first_start = _span_key(first)[:2]
    first_end = _span_key(first)[2:]
    second_start = _span_key(second)[:2]
    second_end = _span_key(second)[2:]
    return first_start <= second_end and second_start <= first_end
