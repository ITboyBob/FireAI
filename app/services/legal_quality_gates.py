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


RULESET_VERSION = "legal-quality-v3"

S3_TAIL_MARKER_PATTERNS = (
    re.compile(r"PAGE\s*\\\s*\*\s*MERGEFORMAT"),
    re.compile(r"NUMPAGES"),
    re.compile(r"HYPERLINK"),
    re.compile(r"姓名[：:]"),
    re.compile(r"单位[：:]"),
    re.compile(r"行政执法监督文书"),
)

REVISION_SIGNAL_PATTERN = re.compile(r"修正|修订|修改")
MULTI_AUTHORITY_SIGNAL_PATTERN = re.compile(r"[；;]|联合|会同")

ARTICLE_IN_TEXT_PATTERN = re.compile(
    r"^第([一二三四五六七八九十百千万零〇两0-9]+)条(?:\s|　|$)",
    re.MULTILINE,
)
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

    if quality_input.content_class is ContentClass.S2:
        gates.append(_gate_s2_leading_material_isolation(quality_input))
        gates.append(_gate_s2_metadata_traceability(quality_input))

    if quality_input.content_class is ContentClass.S3:
        gates.append(_gate_s3_tail_exclusion_presence(quality_input))
        gates.append(_gate_s3_tail_position(quality_input))
        gates.append(_gate_s3_tail_coverage(quality_input))
        gates.append(_gate_s3_output_purity(quality_input))

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


def _gate_s2_leading_material_isolation(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S2:
        return GateResult(
            gate_id="s2_leading_material_isolation",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S2"},
            evidence_refs=(),
        )

    intermediate = quality_input.intermediate
    excluded_ranges = intermediate.extraction_report.excluded_ranges
    leading_ranges = [
        r for r in excluded_ranges if r.kind == "leading_publication_material"
    ]
    if not leading_ranges:
        return GateResult(
            gate_id="s2_leading_material_isolation",
            outcome=GateOutcome.FAIL,
            measured={"leading_range_count": 0},
            evidence_refs=(),
            reason_code="missing_leading_material_exclusion",
        )

    boundary_start = _position_key(intermediate.boundary.start, 0)
    body_unit_spans = [unit.source_span for unit in intermediate.body_units]
    block_text_by_order = {
        block.order: block.text for block in quality_input.extraction.text_blocks
    }
    target_article_numbers = _article_numbers_in_units(intermediate.body_units)

    overlaps: list[str] = []
    leading_article_conflicts: list[str] = []
    for excluded in leading_ranges:
        excluded_end = _position_key(
            excluded.source_span.end,
            excluded.source_span.end_char_offset,
        )
        if excluded_end > boundary_start:
            overlaps.append(
                f"{excluded.kind}:end_after_boundary:{excluded_end}>{boundary_start}"
            )
        for unit_span in body_unit_spans:
            if _spans_overlap(excluded.source_span, unit_span):
                overlaps.append(f"{excluded.kind}:overlaps_body")
                break
        excluded_text = _extract_excluded_text(
            excluded.source_span, block_text_by_order
        )
        excluded_numbers = _article_numbers_in_text(excluded_text)
        conflict = target_article_numbers & excluded_numbers
        if conflict:
            leading_article_conflicts.append(
                f"conflict_numbers:{sorted(conflict)}"
            )

    if overlaps:
        return GateResult(
            gate_id="s2_leading_material_isolation",
            outcome=GateOutcome.FAIL,
            measured={"overlaps": overlaps},
            evidence_refs=tuple(overlaps),
            reason_code="leading_material_overlaps_body",
        )

    if leading_article_conflicts:
        return GateResult(
            gate_id="s2_leading_material_isolation",
            outcome=GateOutcome.FAIL,
            measured={"leading_article_conflicts": leading_article_conflicts},
            evidence_refs=tuple(leading_article_conflicts),
            reason_code="leading_article_numbers_in_body",
        )

    return GateResult(
        gate_id="s2_leading_material_isolation",
        outcome=GateOutcome.PASS,
        measured={"leading_range_count": len(leading_ranges)},
        evidence_refs=(),
    )


def _gate_s2_metadata_traceability(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S2:
        return GateResult(
            gate_id="s2_metadata_traceability",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S2"},
            evidence_refs=(),
        )

    intermediate = quality_input.intermediate
    target = intermediate.target
    block_text_by_order = {
        block.order: block.text for block in quality_input.extraction.text_blocks
    }

    target_values = {
        "issuing_authority": target.issuing_authority,
        "promulgated_on": target.promulgated_on,
        "effective_on": target.effective_on,
        "revision_events": target.revision_events,
        "version_basis": target.version_basis,
    }
    valued_fields = {
        field
        for field, value in target_values.items()
        if value is not None and value != ()
    }
    evidence_by_field: dict[str, list[MetadataEvidence]] = {
        field: [] for field in ALLOWED_METADATA_EVIDENCE_FIELDS
    }
    for evidence in target.evidence:
        evidence_by_field[evidence.field_name].append(evidence)

    for evidence in target.evidence:
        if evidence.field_name not in ALLOWED_METADATA_EVIDENCE_FIELDS:
            return GateResult(
                gate_id="s2_metadata_traceability",
                outcome=GateOutcome.FAIL,
                measured={"invalid_field": evidence.field_name},
                evidence_refs=(evidence.field_name,),
                reason_code="invalid_evidence_field",
            )
        if not _is_span_within_blocks(
            evidence.source_span, block_text_by_order
        ):
            return GateResult(
                gate_id="s2_metadata_traceability",
                outcome=GateOutcome.FAIL,
                measured={
                    "field": evidence.field_name,
                    "span": str(evidence.source_span),
                },
                evidence_refs=(evidence.field_name,),
                reason_code="evidence_span_invalid",
            )
        expected_value = target_values[evidence.field_name]
        if evidence.field_name == "revision_events":
            if evidence.value not in expected_value:
                return GateResult(
                    gate_id="s2_metadata_traceability",
                    outcome=GateOutcome.FAIL,
                    measured={
                        "field": evidence.field_name,
                        "expected": expected_value,
                        "actual": evidence.value,
                    },
                    evidence_refs=(evidence.field_name,),
                    reason_code="evidence_value_mismatch",
                )
        elif evidence.value != expected_value:
            return GateResult(
                gate_id="s2_metadata_traceability",
                outcome=GateOutcome.FAIL,
                measured={
                    "field": evidence.field_name,
                    "expected": expected_value,
                    "actual": evidence.value,
                },
                evidence_refs=(evidence.field_name,),
                reason_code="evidence_value_mismatch",
            )

    missing_evidence = {
        field
        for field in valued_fields
        if not evidence_by_field.get(field)
    }
    if missing_evidence:
        return GateResult(
            gate_id="s2_metadata_traceability",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"fields_without_evidence": sorted(missing_evidence)},
            evidence_refs=tuple(sorted(missing_evidence)),
            reason_code="metadata_value_without_evidence",
        )

    if target.issuing_authority and MULTI_AUTHORITY_SIGNAL_PATTERN.search(
        target.issuing_authority
    ):
        authority_evidence = evidence_by_field.get("issuing_authority", ())
        date_evidence = evidence_by_field.get("promulgated_on", ())
        if not any(
            ev.extraction_status == "confirmed" for ev in authority_evidence
        ) or not any(
            ev.extraction_status == "confirmed" for ev in date_evidence
        ):
            return GateResult(
                gate_id="s2_metadata_traceability",
                outcome=GateOutcome.REVIEW_REQUIRED,
                measured={
                    "multi_authority_signal": True,
                    "authority_confirmed": any(
                        ev.extraction_status == "confirmed"
                        for ev in authority_evidence
                    ),
                    "date_confirmed": any(
                        ev.extraction_status == "confirmed"
                        for ev in date_evidence
                    ),
                },
                evidence_refs=(),
                reason_code="multi_authority_without_confirmed_evidence",
            )

    if any(
        evidence.extraction_status == "review_required"
        for evidence in target.evidence
    ):
        return GateResult(
            gate_id="s2_metadata_traceability",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"review_required_evidence_fields": sorted(
                {ev.field_name for ev in target.evidence if ev.extraction_status == "review_required"}
            )},
            evidence_refs=(),
            reason_code="metadata_evidence_review_required",
        )

    extraction_text = "\n".join(block.text for block in quality_input.extraction.text_blocks)
    if (
        REVISION_SIGNAL_PATTERN.search(extraction_text)
        and not target.revision_events
        and target.version_basis is None
    ):
        return GateResult(
            gate_id="s2_metadata_traceability",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"revision_signal": True},
            evidence_refs=(),
            reason_code="revision_signal_without_traceability",
        )

    return GateResult(
        gate_id="s2_metadata_traceability",
        outcome=GateOutcome.PASS,
        measured={"evidence_field_count": len(target.evidence)},
        evidence_refs=tuple(
            f"{ev.field_name}:block:{ev.source_span.start.block_order}"
            for ev in target.evidence
        ),
    )


def _gate_s3_tail_exclusion_presence(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S3:
        return GateResult(
            gate_id="s3_tail_exclusion_presence",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S3"},
            evidence_refs=(),
        )

    excluded_ranges = quality_input.intermediate.extraction_report.excluded_ranges
    tail_ranges = [
        r
        for r in excluded_ranges
        if r.kind
        in {
            "attachment_index",
            "form_template",
            "score_table",
            "trailing_print_metadata",
            "word_page_field",
        }
    ]
    if not tail_ranges:
        return GateResult(
            gate_id="s3_tail_exclusion_presence",
            outcome=GateOutcome.FAIL,
            measured={"tail_range_count": 0},
            evidence_refs=(),
            reason_code="missing_tail_exclusion",
        )

    return GateResult(
        gate_id="s3_tail_exclusion_presence",
        outcome=GateOutcome.PASS,
        measured={
            "tail_range_count": len(tail_ranges),
            "tail_ranges": [
                {
                    "kind": r.kind,
                    "start": r.source_span.start.block_order,
                    "end": r.source_span.end.block_order,
                }
                for r in tail_ranges
            ],
        },
        evidence_refs=tuple(f"{r.kind}:{r.source_span.start.block_order}" for r in tail_ranges),
    )


def _gate_s3_tail_position(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S3:
        return GateResult(
            gate_id="s3_tail_position",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S3"},
            evidence_refs=(),
        )

    excluded_ranges = quality_input.intermediate.extraction_report.excluded_ranges
    if not excluded_ranges:
        return GateResult(
            gate_id="s3_tail_position",
            outcome=GateOutcome.PASS,
            measured={"skipped": "no_excluded_ranges"},
            evidence_refs=(),
        )

    body_units = quality_input.intermediate.body_units
    if not body_units:
        return GateResult(
            gate_id="s3_tail_position",
            outcome=GateOutcome.PASS,
            measured={"skipped": "no_body_units"},
            evidence_refs=(),
        )

    last_unit = body_units[-1]
    body_end = _position_key(
        last_unit.source_span.end,
        last_unit.source_span.end_char_offset,
    )

    for excluded in excluded_ranges:
        excluded_start = _position_key(
            excluded.source_span.start,
            excluded.source_span.start_char_offset,
        )
        if excluded_start <= body_end:
            return GateResult(
                gate_id="s3_tail_position",
                outcome=GateOutcome.FAIL,
                measured={
                    "body_end": body_end,
                    "excluded_start": excluded_start,
                    "excluded_kind": excluded.kind,
                },
                evidence_refs=(f"{excluded.kind}:{excluded_start}",),
                reason_code="tail_exclusion_before_body",
            )

    for index in range(len(excluded_ranges) - 1):
        prev_end = _position_key(
            excluded_ranges[index].source_span.end,
            excluded_ranges[index].source_span.end_char_offset,
        )
        next_start = _position_key(
            excluded_ranges[index + 1].source_span.start,
            excluded_ranges[index + 1].source_span.start_char_offset,
        )
        if next_start <= prev_end:
            return GateResult(
                gate_id="s3_tail_position",
                outcome=GateOutcome.FAIL,
                measured={
                    "prev_end": prev_end,
                    "next_start": next_start,
                    "prev_kind": excluded_ranges[index].kind,
                    "next_kind": excluded_ranges[index + 1].kind,
                },
                evidence_refs=(),
                reason_code="tail_exclusion_out_of_order",
            )

    return GateResult(
        gate_id="s3_tail_position",
        outcome=GateOutcome.PASS,
        measured={"tail_range_count": len(excluded_ranges)},
        evidence_refs=(),
    )


def _gate_s3_tail_coverage(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S3:
        return GateResult(
            gate_id="s3_tail_coverage",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S3"},
            evidence_refs=(),
        )

    excluded_ranges = quality_input.intermediate.extraction_report.excluded_ranges
    if not excluded_ranges:
        return GateResult(
            gate_id="s3_tail_coverage",
            outcome=GateOutcome.PASS,
            measured={"skipped": "no_excluded_ranges"},
            evidence_refs=(),
        )

    blocks = quality_input.extraction.text_blocks
    if not blocks:
        return GateResult(
            gate_id="s3_tail_coverage",
            outcome=GateOutcome.PASS,
            measured={"skipped": "no_blocks"},
            evidence_refs=(),
        )

    tail_start = min(r.source_span.start.block_order for r in excluded_ranges)
    non_empty_after_tail = {
        block.order
        for block in blocks[tail_start:]
        if block.text.strip()
    }

    covered: set[int] = set()
    for excluded in excluded_ranges:
        for order in range(
            excluded.source_span.start.block_order,
            excluded.source_span.end.block_order + 1,
        ):
            covered.add(order)

    missing = sorted(non_empty_after_tail - covered)
    if missing:
        return GateResult(
            gate_id="s3_tail_coverage",
            outcome=GateOutcome.REVIEW_REQUIRED,
            measured={"unclassified_blocks": missing},
            evidence_refs=tuple(f"block:{order}" for order in missing),
            reason_code="unclassified_tail_block",
        )

    return GateResult(
        gate_id="s3_tail_coverage",
        outcome=GateOutcome.PASS,
        measured={
            "tail_range_count": len(excluded_ranges),
            "covered_block_count": len(covered),
        },
        evidence_refs=(),
    )


def _gate_s3_output_purity(quality_input: QualityInput) -> GateResult:
    if quality_input.content_class is not ContentClass.S3:
        return GateResult(
            gate_id="s3_output_purity",
            outcome=GateOutcome.PASS,
            measured={"skipped": "not_S3"},
            evidence_refs=(),
        )

    contaminants: list[dict[str, str]] = []

    def _check_text(text: str, location: str) -> None:
        for pattern in S3_TAIL_MARKER_PATTERNS:
            if pattern.search(text):
                contaminants.append({"location": location, "pattern": pattern.pattern})
                break

    _check_text(quality_input.intermediate.body_text, "body_text")
    for article in quality_input.parsed.articles:
        _check_text(article.text, f"article:{article.article_no}")
    for index, chunk in enumerate(quality_input.chunks):
        _check_text(chunk.get("text", ""), f"chunk:{index}")

    if contaminants:
        reason_code = (
            "tail_marker_in_body"
            if contaminants[0]["location"] == "body_text"
            else "tail_marker_in_chunk"
        )
        return GateResult(
            gate_id="s3_output_purity",
            outcome=GateOutcome.FAIL,
            measured={"contaminants": contaminants},
            evidence_refs=tuple(f"{c['location']}:{c['pattern']}" for c in contaminants),
            reason_code=reason_code,
        )

    return GateResult(
        gate_id="s3_output_purity",
        outcome=GateOutcome.PASS,
        measured={"contaminant_count": 0},
        evidence_refs=(),
    )


ALLOWED_METADATA_EVIDENCE_FIELDS = {
    "issuing_authority",
    "promulgated_on",
    "effective_on",
    "revision_events",
    "version_basis",
}


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


def _position_key(location, char_offset: int) -> tuple[int, int]:
    return (location.block_order, char_offset)


def _span_key(span) -> tuple[int, int, int, int]:
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


def _extract_excluded_text(
    span,
    block_text_by_order: dict[int, str],
) -> str:
    start_order = span.start.block_order
    end_order = span.end.block_order
    if start_order not in block_text_by_order or end_order not in block_text_by_order:
        return ""

    start_text = block_text_by_order[start_order]
    end_text = block_text_by_order[end_order]
    start_offset = min(span.start_char_offset, len(start_text))
    end_offset = min(span.end_char_offset, len(end_text))

    if start_order == end_order:
        return start_text[start_offset:end_offset]

    parts = [start_text[start_offset:]]
    for order in range(start_order + 1, end_order):
        text = block_text_by_order.get(order)
        if text is not None:
            parts.append(text)
    parts.append(end_text[:end_offset])
    return "\n".join(parts)


def _article_numbers_in_units(units) -> set[int]:
    numbers: set[int] = set()
    for unit in units:
        if unit.kind != "article":
            continue
        match = ARTICLE_PATTERN.match(unit.text)
        if match is not None:
            numbers.add(_article_number_value(match.group(1)))
    return numbers


def _article_numbers_in_text(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in ARTICLE_IN_TEXT_PATTERN.finditer(text):
        numbers.add(_article_number_value(match.group(1)))
    return numbers


def _is_span_within_blocks(
    span,
    block_text_by_order: dict[int, str],
) -> bool:
    start_order = span.start.block_order
    end_order = span.end.block_order
    if start_order not in block_text_by_order or end_order not in block_text_by_order:
        return False
    start_text = block_text_by_order[start_order]
    end_text = block_text_by_order[end_order]
    if not (
        0 <= span.start_char_offset <= len(start_text)
        and 0 <= span.end_char_offset <= len(end_text)
    ):
        return False
    if end_order < start_order:
        return False
    return True
