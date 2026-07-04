from dataclasses import dataclass

from app.services.corpus_ingestor import build_document_id
from app.services.legal_boundary_common import (
    ARTICLE_PATTERN,
    HEADING_PATTERN,
    article_number,
    build_body_units,
    find_tail_boundary,
    is_footer_line,
    is_tail_marker,
    normalize_title,
)
from app.services.legal_extractor import (
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
    SourceSpan,
    TargetMetadata,
    validate_legal_intermediate,
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

    normalized_expected = normalize_title(expected_title)
    title_indexes = tuple(
        index
        for index, block in enumerate(blocks)
        if normalize_title(block.text) == normalized_expected
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
    if not article_indexes or article_number(blocks[article_indexes[0]]) != 1:
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="first_article_missing",
        )
    article_numbers = tuple(article_number(blocks[index]) for index in article_indexes)
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
        is_tail_marker(blocks[index].text.strip())
        for index in range(first_article_index, last_article_index)
    ):
        return _review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="tail_noise_inside_article_block",
        )

    tail_start, body_end, tail_ambiguous = find_tail_boundary(
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

    body_units = build_body_units(
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
