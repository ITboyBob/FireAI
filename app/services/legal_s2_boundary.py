import re
from dataclasses import dataclass

from app.services.corpus_ingestor import build_document_id
from app.services.legal_content_boundary import (
    ARTICLE_PATTERN,
    HEADING_PATTERN,
    _article_number,
    _build_body_units,
    _chinese_number_to_int,
    _find_tail_boundary,
    _is_footer_line,
    _is_tail_marker,
    _normalize_title,
)
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
    BoundaryDecision,
    ExcludedRange,
    ExtractionReport,
    LegalDocumentIntermediate,
    MetadataEvidence,
    SourceSpan,
    TargetMetadata,
    validate_legal_intermediate,
)


ARABIC_DATE_PATTERN = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"
)
CHINESE_DATE_PATTERN = re.compile(
    r"[一二三四五六七八九十〇○零]+年"
    r"[一二三四五六七八九十〇○零]+月"
    r"[一二三四五六七八九十〇○零]+日"
)
EFFECTIVE_DATE_PATTERN = re.compile(
    r"自\s*(.+?)\s*起施(?:行|实施)"
)
AUTHORITY_TOKEN_PATTERN = re.compile(
    r"(?:人民政府|办公厅|办公室|部|委员会|总局|局)"
)


@dataclass(frozen=True, slots=True)
class S2BoundaryStrategy:
    kind: str = ContentClass.S2.value
    version: str = "s2-boundary-v1"

    def identify(
        self,
        extraction: ExtractionResult,
        *,
        source: SourceRef,
        expected_title: str | None = None,
    ) -> LegalDocumentIntermediate:
        return identify_s2_target_body(
            extraction,
            source=source,
            expected_title=expected_title or source.source_path.stem,
        )


def identify_s2_target_body(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
) -> LegalDocumentIntermediate:
    if extraction.disposition is not IngestionDisposition.READY:
        return _s2_blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="extraction_not_ready",
        )
    if extraction.source_sha256 != source.source_sha256:
        return _s2_blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="source_digest_mismatch",
        )
    blocks = extraction.text_blocks
    if tuple(block.order for block in blocks) != tuple(range(len(blocks))):
        return _s2_blocked_intermediate(
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
        return _s2_review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="title_not_found",
        )

    if len(title_indexes) == 1:
        feasible, reason, candidate = _evaluate_candidate(
            blocks,
            title_index=title_indexes[0],
            region_end=len(blocks),
        )
        if not feasible:
            return _s2_review(
                extraction,
                source=source,
                expected_title=expected_title,
                reason=reason or "title_candidate_ambiguous",
            )
    else:
        feasible_candidates: list[dict] = []
        for candidate_index, title_index in enumerate(title_indexes):
            region_end = (
                title_indexes[candidate_index + 1]
                if candidate_index + 1 < len(title_indexes)
                else len(blocks)
            )
            feasible, _, candidate = _evaluate_candidate(
                blocks,
                title_index=title_index,
                region_end=region_end,
            )
            if feasible:
                feasible_candidates.append(candidate)
        if len(feasible_candidates) != 1:
            return _s2_review(
                extraction,
                source=source,
                expected_title=expected_title,
                reason="title_candidate_ambiguous",
            )
        candidate = feasible_candidates[0]

    title_index = candidate["title_index"]
    first_article_index = candidate["first_article_index"]
    body_end = candidate["body_end"]
    tail_start = candidate["tail_start"]

    body_units = _build_body_units(
        blocks,
        title_index=title_index,
        first_article_index=first_article_index,
        body_end=body_end,
        expected_title=expected_title,
    )
    if not body_units:
        return _s2_review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="body_units_empty",
        )

    excluded_ranges = _s2_excluded_ranges(
        blocks,
        title_index=title_index,
        tail_start=tail_start,
    )

    metadata = _extract_metadata(
        blocks,
        title_index=title_index,
        first_article_index=first_article_index,
    )

    boundary_start = blocks[title_index].location
    boundary_end = body_units[-1].source_span.end
    coverage = SourceSpan(
        start=boundary_start,
        end=boundary_end,
        start_char_offset=0,
        end_char_offset=body_units[-1].source_span.end_char_offset,
    )

    extraction_class = (
        ExtractionClass(extraction.extractor_kind)
        if extraction.extractor_kind in {item.value for item in ExtractionClass}
        else ExtractionClass.PX
    )
    intermediate = LegalDocumentIntermediate(
        schema_version="legal-intermediate-v2",
        document_id=build_document_id(expected_title),
        source_ref=source,
        extraction_class=extraction_class,
        content_class=ContentClass.S2,
        target=TargetMetadata(
            title=expected_title,
            issuing_authority=metadata.get("issuing_authority"),
            promulgated_on=metadata.get("promulgated_on"),
            effective_on=metadata.get("effective_on"),
            revision_events=metadata.get("revision_events", ()),
            evidence=metadata.get("evidence", ()),
        ),
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
                f"continuous_last_article:block:{candidate['last_article_index']}",
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


def _evaluate_candidate(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
    region_end: int,
) -> tuple[bool, str | None, dict | None]:
    article_indexes = tuple(
        index
        for index in range(title_index + 1, region_end)
        if ARTICLE_PATTERN.match(blocks[index].text.strip())
    )
    if not article_indexes:
        return False, "first_article_missing", None
    if _article_number(blocks[article_indexes[0]]) != 1:
        return False, "first_article_missing", None
    article_numbers = tuple(
        _article_number(blocks[index]) for index in article_indexes
    )
    if article_numbers != tuple(range(1, len(article_numbers) + 1)):
        return False, "article_sequence_broken", None
    first_article_index = article_indexes[0]
    last_article_index = article_indexes[-1]
    if any(
        _is_tail_marker(blocks[index].text.strip())
        for index in range(first_article_index, last_article_index)
    ):
        return False, "tail_noise_inside_article_block", None

    tail_start, body_end, tail_ambiguous = _find_tail_boundary_in_region(
        blocks,
        last_article_index=last_article_index,
        region_end=region_end,
    )
    if tail_ambiguous:
        return False, "trailing_content_ambiguous", None

    return True, None, {
        "title_index": title_index,
        "first_article_index": first_article_index,
        "last_article_index": last_article_index,
        "body_end": body_end,
        "tail_start": tail_start,
    }


def _find_tail_boundary_in_region(
    blocks: tuple[ExtractedBlock, ...],
    *,
    last_article_index: int,
    region_end: int,
) -> tuple[int | None, int, bool]:
    tail_start: int | None = None
    body_end = last_article_index
    blank_seen = False
    for index in range(last_article_index + 1, region_end):
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


def _s2_excluded_ranges(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
    tail_start: int | None,
) -> tuple[ExcludedRange, ...]:
    ranges: list[ExcludedRange] = []
    if title_index > 0:
        final_leading_block = blocks[title_index - 1]
        ranges.append(
            ExcludedRange(
                source_span=SourceSpan(
                    start=blocks[0].location,
                    end=final_leading_block.location,
                    start_char_offset=0,
                    end_char_offset=len(final_leading_block.text),
                ),
                kind="leading_publication_material",
                reason="publication_and_revision_material_before_target_title",
            )
        )
    if tail_start is not None:
        final_block = blocks[-1]
        ranges.append(
            ExcludedRange(
                source_span=SourceSpan(
                    start=blocks[tail_start].location,
                    end=final_block.location,
                    start_char_offset=0,
                    end_char_offset=len(final_block.text),
                ),
                kind="trailing_noise",
                reason="footer_print_or_page_field_after_last_article",
            )
        )
    return tuple(ranges)


def _extract_metadata(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
    first_article_index: int,
) -> dict:
    evidence: list[MetadataEvidence] = []
    values: dict = {}
    leading_blocks = blocks[:title_index]
    version_blocks = tuple(
        block
        for block in blocks[title_index + 1 : first_article_index]
        if block.text.strip()
    )

    authority, authority_span = _extract_issuing_authority(leading_blocks)
    if authority:
        values["issuing_authority"] = authority
        evidence.append(
            MetadataEvidence(
                field_name="issuing_authority",
                value=authority,
                source_span=authority_span,
                extraction_status="confirmed",
            )
        )

    promulgated_date, promulgated_span = _extract_promulgated_date(
        leading_blocks, version_blocks
    )
    if promulgated_date:
        values["promulgated_on"] = promulgated_date
        evidence.append(
            MetadataEvidence(
                field_name="promulgated_on",
                value=promulgated_date,
                source_span=promulgated_span,
                extraction_status="confirmed",
            )
        )

    effective_date, effective_span = _extract_effective_date(
        leading_blocks + version_blocks
    )
    if effective_date:
        values["effective_on"] = effective_date
        evidence.append(
            MetadataEvidence(
                field_name="effective_on",
                value=effective_date,
                source_span=effective_span,
                extraction_status="confirmed",
            )
        )

    revision_events = _extract_revision_events(leading_blocks + version_blocks)
    if revision_events:
        values["revision_events"] = tuple(event["value"] for event in revision_events)
        for event in revision_events:
            evidence.append(
                MetadataEvidence(
                    field_name="revision_events",
                    value=event["value"],
                    source_span=event["span"],
                    extraction_status="confirmed",
                )
            )

    values["evidence"] = tuple(evidence)
    return values


def _extract_promulgated_date(
    leading_blocks: tuple[ExtractedBlock, ...],
    version_blocks: tuple[ExtractedBlock, ...],
) -> tuple[str | None, SourceSpan | None]:
    # 优先从标题与第一条之间的版本说明中找“公布”日期
    for block in version_blocks:
        if "公布" not in block.text:
            continue
        date_match = _last_date_match(block.text)
        if date_match is not None:
            value = date_match.group(0)
            return value, _single_block_span(block, date_match.start(), len(value))

    last_match: tuple[str, ExtractedBlock, int] | None = None
    for block in leading_blocks:
        text = block.text
        date_match = _last_date_match(text)
        if date_match is not None:
            last_match = (date_match.group(0), block, date_match.start())
    if last_match is None:
        return None, None
    value, block, start = last_match
    return value, _single_block_span(block, start, len(value))


def _last_date_match(text: str) -> re.Match | None:
    last_match: re.Match | None = None
    for match in CHINESE_DATE_PATTERN.finditer(text):
        last_match = match
    for match in ARABIC_DATE_PATTERN.finditer(text):
        last_match = match
    return last_match


def _extract_effective_date(
    blocks: tuple[ExtractedBlock, ...]
) -> tuple[str | None, SourceSpan | None]:
    for block in blocks:
        match = EFFECTIVE_DATE_PATTERN.search(block.text)
        if match is None:
            continue
        date_text = match.group(1)
        date_match = ARABIC_DATE_PATTERN.search(date_text) or CHINESE_DATE_PATTERN.search(
            date_text
        )
        if date_match is None:
            continue
        value = date_match.group(0)
        return value, _single_block_span(
            block, match.start(1) + date_match.start(), len(value)
        )
    return None, None


def _extract_revision_events(
    blocks: tuple[ExtractedBlock, ...]
) -> list[dict]:
    events: list[dict] = []
    for block in blocks:
        text = block.text.strip()
        if "修正" in text or "修订" in text:
            value = text
            events.append(
                {
                    "value": value,
                    "span": _single_block_span(block, 0, len(block.text)),
                }
            )
    return events


def _extract_issuing_authority(
    blocks: tuple[ExtractedBlock, ...]
) -> tuple[str | None, SourceSpan | None]:
    candidate_blocks: list[ExtractedBlock] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            if candidate_blocks:
                break
            continue
        if "通过" in text or "施行" in text or _contains_date(text):
            break
        if AUTHORITY_TOKEN_PATTERN.search(text):
            candidate_blocks.append(block)
        elif candidate_blocks:
            break

    if not candidate_blocks:
        return None, None

    cleaned = []
    for block in candidate_blocks:
        text = block.text.strip().rstrip("令")
        text = text.strip().rstrip("、；;")
        if text:
            cleaned.append(text)
    if not cleaned:
        return None, None

    value = "；".join(cleaned)
    start_block = candidate_blocks[0]
    end_block = candidate_blocks[-1]
    span = SourceSpan(
        start=start_block.location,
        end=end_block.location,
        start_char_offset=0,
        end_char_offset=len(end_block.text),
    )
    return value, span


def _contains_date(text: str) -> bool:
    return bool(
        ARABIC_DATE_PATTERN.search(text) or CHINESE_DATE_PATTERN.search(text)
    )


def _single_block_span(
    block: ExtractedBlock,
    start_offset: int,
    length: int,
) -> SourceSpan:
    return SourceSpan(
        start=block.location,
        end=block.location,
        start_char_offset=start_offset,
        end_char_offset=start_offset + length,
    )


def _s2_review(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
    reason: str,
) -> LegalDocumentIntermediate:
    return _s2_blocked_intermediate(
        extraction,
        source=source,
        expected_title=expected_title,
        status="review_required",
        reason=reason,
    )


def _s2_blocked_intermediate(
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
        schema_version="legal-intermediate-v2",
        document_id=build_document_id(expected_title),
        source_ref=source,
        extraction_class=extraction_class,
        content_class=ContentClass.S2,
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
