from dataclasses import dataclass
import re
import unicodedata

from app.services.corpus_ingestor import build_document_id
from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    SourceRef,
)
from app.services.legal_intermediate import (
    BodyUnit,
    BoundaryDecision,
    ExcludedRange,
    ExtractionReport,
    LegalDocumentIntermediate,
    SourceSpan,
    TargetMetadata,
    validate_legal_intermediate,
)


ARTICLE_PATTERN = re.compile(
    r"^第([一二三四五六七八九十百千万零〇两0-9]+)条(?:\s|　|$)"
)
HEADING_PATTERN = re.compile(
    r"^第[一二三四五六七八九十百千万零〇两0-9]+([编章节])(?:\s|　|$)"
)
PAGE_FIELD_PATTERN = re.compile(r"(?:PAGE|MERGEFORMAT)")
PAGE_LINE_PATTERN = re.compile(r"^第?\s*\d+\s*页?$")
PRINT_RECORD_PATTERN = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*印发[。.]?$"
)
COPY_DISTRIBUTION_PATTERN = re.compile(r"^抄送\s*[：:]")
ADMIN_OFFICE_FOOTER_PATTERN = re.compile(
    r"^[^，,；;：:]{2,40}(?:办公室|办公厅)[。.]?$"
)


@dataclass(frozen=True, slots=True)
class S1BoundaryStrategy:
    kind: str = ContentClass.S1.value
    version: str = "s1-boundary-v1"

    def identify(
        self,
        extraction: ExtractionResult,
        *,
        source: SourceRef,
        expected_title: str | None = None,
    ) -> LegalDocumentIntermediate:
        return identify_s1_target_body(
            extraction,
            source=source,
            expected_title=expected_title or source.source_path.stem,
        )


def identify_s1_target_body(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
) -> LegalDocumentIntermediate:
    if extraction.disposition is not IngestionDisposition.READY:
        return _blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="extraction_not_ready",
        )
    if extraction.source_sha256 != source.source_sha256:
        return _blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="source_digest_mismatch",
        )
    blocks = extraction.text_blocks
    if tuple(block.order for block in blocks) != tuple(range(len(blocks))):
        return _blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="block_order_invalid",
        )

    normalized_expected = _normalize_title(expected_title)
    title_indexes = tuple(
        index
        for index, block in enumerate(blocks)
        if _normalize_title(block.text) == normalized_expected
    )
    if not title_indexes:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="title_not_found",
        )
    if len(title_indexes) != 1:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="title_not_unique",
        )
    title_index = title_indexes[0]

    article_indexes = tuple(
        index
        for index in range(title_index + 1, len(blocks))
        if ARTICLE_PATTERN.match(blocks[index].text.strip())
    )
    if not article_indexes or _article_number(blocks[article_indexes[0]]) != 1:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="first_article_missing",
        )
    article_numbers = tuple(_article_number(blocks[index]) for index in article_indexes)
    if article_numbers != tuple(range(1, len(article_numbers) + 1)):
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="article_sequence_broken",
        )
    first_article_index = article_indexes[0]
    last_article_index = article_indexes[-1]
    if any(
        _is_tail_marker(blocks[index].text.strip())
        for index in range(first_article_index, last_article_index)
    ):
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="tail_noise_inside_article_block",
        )

    tail_start, body_end, tail_ambiguous = _find_tail_boundary(
        blocks,
        last_article_index=last_article_index,
    )
    if tail_ambiguous:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="trailing_content_ambiguous",
        )

    body_units = _build_body_units(
        blocks,
        title_index=title_index,
        first_article_index=first_article_index,
        body_end=body_end,
        expected_title=expected_title,
    )
    if not body_units:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="body_units_empty",
        )
    excluded_ranges = _excluded_tail_range(blocks, tail_start=tail_start)
    boundary_start = blocks[title_index].location
    boundary_end = body_units[-1].source_span.end
    coverage = SourceSpan(
        start=boundary_start,
        end=boundary_end,
        start_char_offset=0,
        end_char_offset=body_units[-1].source_span.end_char_offset,
    )
    extraction_class = ExtractionClass(extraction.extractor_kind)
    intermediate = LegalDocumentIntermediate(
        schema_version="legal-intermediate-v1",
        document_id=build_document_id(expected_title),
        source_ref=source,
        extraction_class=extraction_class,
        content_class=ContentClass.S1,
        target=TargetMetadata(title=expected_title),
        boundary=BoundaryDecision(
            status="confirmed",
            start=boundary_start,
            end=boundary_end,
            title_evidence=(
                f"expected_title_exact_match:block:{blocks[title_index].order}",
            ),
            start_evidence=(
                f"first_article:block:{blocks[first_article_index].order}",
            ),
            end_evidence=(
                f"continuous_last_article:block:{blocks[last_article_index].order}",
            ),
        ),
        body_text="\n".join(unit.text for unit in body_units),
        body_units=body_units,
        diagnostics=tuple(extraction.warnings),
        extraction_report=ExtractionReport(
            status="confirmed",
            extractor_kind=extraction.extractor_kind,
            extractor_version=extraction.extractor_version,
            excluded_ranges=excluded_ranges,
            warnings=tuple(extraction.warnings),
            source_coverage=coverage,
        ),
    )
    validate_legal_intermediate(intermediate)
    return intermediate


def _find_tail_boundary(
    blocks: tuple[ExtractedBlock, ...],
    *,
    last_article_index: int,
) -> tuple[int | None, int, bool]:
    tail_start: int | None = None
    body_end = last_article_index
    blank_seen = False
    for index in range(last_article_index + 1, len(blocks)):
        text = blocks[index].text.strip()
        if tail_start is not None:
            continue
        if not text:
            blank_seen = True
            continue
        if _is_tail_marker(text) or (blank_seen and _is_footer_line(text)):
            tail_start = index
            continue
        if blank_seen:
            return None, body_end, True
        body_end = index
    return tail_start, body_end, False


def _build_body_units(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
    first_article_index: int,
    body_end: int,
    expected_title: str,
) -> tuple[BodyUnit, ...]:
    units: list[BodyUnit] = [
        _body_unit(
            block=blocks[title_index],
            unit_id="unit-0",
            kind="title",
            text=expected_title,
        )
    ]
    current_parent = "unit-0"
    current_article: str | None = None
    for index in range(title_index + 1, body_end + 1):
        block = blocks[index]
        text = block.text.strip()
        if not text:
            continue
        heading_match = HEADING_PATTERN.match(text)
        article_match = ARTICLE_PATTERN.match(text)
        if index < first_article_index and not heading_match:
            continue
        if heading_match:
            kind = {
                "编": "part",
                "章": "chapter",
                "节": "section",
            }[heading_match.group(1)]
            unit_id = f"unit-{len(units)}"
            units.append(
                _body_unit(
                    block=block,
                    unit_id=unit_id,
                    kind=kind,
                    text=text,
                    parent_unit_id="unit-0",
                )
            )
            current_parent = unit_id
            continue
        if article_match:
            unit_id = f"unit-{len(units)}"
            units.append(
                _body_unit(
                    block=block,
                    unit_id=unit_id,
                    kind="article",
                    text=text,
                    parent_unit_id=current_parent,
                )
            )
            current_article = unit_id
            continue
        if current_article is not None:
            units.append(
                _body_unit(
                    block=block,
                    unit_id=f"unit-{len(units)}",
                    kind="paragraph",
                    text=text,
                    parent_unit_id=current_article,
                )
            )
    return tuple(units)


def _body_unit(
    *,
    block: ExtractedBlock,
    unit_id: str,
    kind: str,
    text: str,
    parent_unit_id: str | None = None,
) -> BodyUnit:
    return BodyUnit(
        unit_id=unit_id,
        kind=kind,
        text=text,
        source_span=SourceSpan(
            start=block.location,
            end=block.location,
            start_char_offset=0,
            end_char_offset=len(block.text),
        ),
        parent_unit_id=parent_unit_id,
    )


def _excluded_tail_range(
    blocks: tuple[ExtractedBlock, ...],
    *,
    tail_start: int | None,
) -> tuple[ExcludedRange, ...]:
    if tail_start is None:
        return ()
    final_block = blocks[-1]
    return (
        ExcludedRange(
            source_span=SourceSpan(
                start=blocks[tail_start].location,
                end=final_block.location,
                start_char_offset=0,
                end_char_offset=len(final_block.text),
            ),
            kind="trailing_noise",
            reason="footer_print_or_page_field_after_last_article",
        ),
    )


def _review(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
    reason: str,
) -> LegalDocumentIntermediate:
    return _blocked_intermediate(
        extraction,
        source=source,
        expected_title=expected_title,
        status="review_required",
        reason=reason,
    )


def _blocked_intermediate(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
    status: str,
    reason: str,
) -> LegalDocumentIntermediate:
    extraction_class = (
        ExtractionClass(extraction.extractor_kind)
        if extraction.extractor_kind in {item.value for item in ExtractionClass}
        else ExtractionClass.PX
    )
    intermediate = LegalDocumentIntermediate(
        schema_version="legal-intermediate-v1",
        document_id=build_document_id(expected_title),
        source_ref=source,
        extraction_class=extraction_class,
        content_class=ContentClass.S1,
        target=TargetMetadata(title=expected_title),
        boundary=BoundaryDecision(
            status=status,
            start=None,
            end=None,
            ambiguities=(reason,),
        ),
        body_text="",
        body_units=(),
        diagnostics=(reason,),
        extraction_report=ExtractionReport(
            status=status,
            extractor_kind=extraction.extractor_kind,
            extractor_version=extraction.extractor_version,
            warnings=tuple(dict.fromkeys((*extraction.warnings, reason))),
        ),
    )
    validate_legal_intermediate(intermediate)
    return intermediate


def _article_number(block: ExtractedBlock) -> int:
    match = ARTICLE_PATTERN.match(block.text.strip())
    if match is None:
        raise ValueError("条文块缺少条号")
    return _chinese_number_to_int(match.group(1))


def _chinese_number_to_int(value: str) -> int:
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


def _normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    return re.sub(r"[\s《》]+", "", normalized)


def _is_tail_marker(text: str) -> bool:
    return (
        bool(PAGE_FIELD_PATTERN.search(text))
        or bool(PAGE_LINE_PATTERN.fullmatch(text))
        or bool(PRINT_RECORD_PATTERN.search(text))
    )


def _is_footer_line(text: str) -> bool:
    return (
        bool(ADMIN_OFFICE_FOOTER_PATTERN.fullmatch(text))
        or bool(COPY_DISTRIBUTION_PATTERN.match(text))
    )
