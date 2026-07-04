"""S3 正文后排除边界策略。

S3 负责处理正文完整出现后，源文件尾部仍包含附件、评分表、考核表、
文书模板或相关印发信息的内容结构。策略先确认唯一目标标题和连续正文，
再识别正文后的实质尾部强信号，最后把尾部材料分类为可审计的排除范围。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

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
    ExtractedBlock,
    ExtractionResult,
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


ATTACHMENT_HEADING_PATTERN = re.compile(r"^(?:附件|附表)\s*[：:：]?$")
FORM_TEMPLATE_TITLE_PATTERN = re.compile(
    r"(?:"
    r".*文书(?:样式|\s*[0-9一二三四五六七八九十]+\s*[：:：]?)"
    r"|.*式样\s*[0-9一二三四五六七八九十]+\s*[：:：]?"
    r"|.*(?:审批表|意见书|认定书|决定书|移送表|登记表|告知书|检查表|处理表)$"
    r")"
)
SCORE_TABLE_PATTERN = re.compile(r"评分表|考核表")
TEMPLATE_FIELD_PATTERN = re.compile(
    r"(?:"
    r"姓\s*名|名\s*称|单\s*位|地\s*址|住\s*址|电\s*话|意\s*见|签\s*名|签\s*字|日\s*期|年\s*月\s*日"
    r"|审\s*批|经\s*办|复\s*核|案\s*由|文\s*号|编\s*号|当\s*事\s*人|个\s*人|字\s*段"
    r"|线\s*索\s*来\s*源|涉\s*案\s*单\s*位|基\s*本\s*情\s*况|处\s*理\s*意\s*见|审\s*批\s*意\s*见"
    r"|案\s*件\s*来\s*源|受\s*审\s*时\s*间|性\s*别|年\s*龄|联\s*系\s*电\s*话"
    r"|主\s*要\s*负\s*责\s*人|简\s*要\s*案\s*情|简\s*要|案\s*情|承\s*办\s*人|部\s*门\s*负\s*责\s*人|审\s*批\s*人"
    r"|法\s*制\s*部\s*门\s*意\s*见|责\s*任\s*人|联\s*系\s*人"
    r"|审\s*查\s*立\s*案\s*时\s*间|审\s*查\s*终\s*结\s*时\s*间|事\s*实|性\s*质|情\s*节"
    r"|社\s*会\s*危\s*害|责\s*任\s*划\s*分|责\s*任\s*追\s*究|纠\s*正|消\s*除\s*危\s*害|救\s*济|时\s*限"
    r"|理\s*由|种\s*类|依\s*据|审\s*查\s*认\s*定\s*机\s*关|机\s*关.*章"
    r"|消[\s\w]*字[\s\w]*号|〔\s*〕[\s\w]*号"
    r"|一\s*式|留\s*存|交\s*.*\s*机\s*构"
    r"|消防\s*救\s*援\s*总\s*队|消防\s*救\s*援\s*支\s*队"
    r")"
)
PRINT_METADATA_PATTERN = re.compile(
    r"(?:\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*印发"
    r"|办公室|办公厅|承办单位|经办人|印数|抄送)"
)
TITLE_FUZZY_THRESHOLD = 0.85


@dataclass(frozen=True, slots=True)
class S3BoundaryStrategy:
    kind: str = ContentClass.S3.value
    version: str = "s3-boundary-v1"

    def identify(
        self,
        extraction: ExtractionResult,
        *,
        source: SourceRef,
        expected_title: str | None = None,
    ) -> LegalDocumentIntermediate:
        return identify_s3_target_body(
            extraction,
            source=source,
            expected_title=expected_title or source.source_path.stem,
        )


def identify_s3_target_body(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
) -> LegalDocumentIntermediate:
    if extraction.disposition is not IngestionDisposition.READY:
        return _s3_blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="extraction_not_ready",
        )
    if extraction.source_sha256 != source.source_sha256:
        return _s3_blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="source_digest_mismatch",
        )
    blocks = extraction.text_blocks
    if tuple(block.order for block in blocks) != tuple(range(len(blocks))):
        return _s3_blocked_intermediate(
            extraction,
            source=source,
            expected_title=expected_title,
            status="rejected",
            reason="block_order_invalid",
        )

    title_index = _find_s3_title(blocks, expected_title)
    if title_index is None:
        return _s3_review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="s3_target_body_ambiguous",
        )

    resolution = _resolve_s3_body_and_tail(blocks, title_index=title_index)
    if not resolution.is_valid:
        return _s3_review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason=resolution.reason,
        )

    body_units = build_body_units(
        blocks,
        title_index=title_index,
        first_article_index=resolution.first_article_index,
        body_end=resolution.body_end,
        expected_title=expected_title,
    )
    if not body_units:
        return _s3_review(
            extraction,
            source=source,
            expected_title=expected_title,
            reason="body_units_empty",
        )

    excluded_ranges = _build_s3_excluded_ranges(
        blocks,
        tail_start=resolution.tail_start,
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
        content_class=ContentClass.S3,
        target=TargetMetadata(title=expected_title),
        boundary=BoundaryDecision(
            status="confirmed",
            start=boundary_start,
            end=boundary_end,
            title_evidence=(
                f"expected_title_match:block:{blocks[title_index].order}",
            ),
            start_evidence=(
                f"first_article:block:{blocks[resolution.first_article_index].order}",
            ),
            end_evidence=(
                f"continuous_last_article:block:{blocks[resolution.last_article_index].order}",
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


@dataclass(frozen=True, slots=True)
class _BodyTailResolution:
    is_valid: bool
    reason: str | None = None
    first_article_index: int = -1
    last_article_index: int = -1
    body_end: int = -1
    tail_start: int | None = None


def _resolve_s3_body_and_tail(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
) -> _BodyTailResolution:
    """同时解析正文条文序列与尾部边界。

    先确认标题后存在连续条文；然后以最后一条为基准寻找 S3 尾部强信号。
    若最后一条之后没有强信号，则逐步向前尝试更早的条文作为正文终点，
    以便检测“条文在尾部之后重新出现”的异常结构。一旦某个候选方案
    检测到尾部之后仍有条文，则直接判定为 ``s3_article_after_tail_start``。
    """
    article_indexes = tuple(
        index
        for index in range(title_index + 1, len(blocks))
        if ARTICLE_PATTERN.match(blocks[index].text.strip())
    )
    if not article_indexes:
        return _BodyTailResolution(is_valid=False, reason="s3_target_body_ambiguous")
    if article_number(blocks[article_indexes[0]]) != 1:
        return _BodyTailResolution(is_valid=False, reason="s3_target_body_ambiguous")
    article_numbers = tuple(
        article_number(blocks[index]) for index in article_indexes
    )
    if article_numbers != tuple(range(1, len(article_numbers) + 1)):
        return _BodyTailResolution(
            is_valid=False, reason="s3_article_sequence_broken"
        )

    first_article_index = article_indexes[0]
    if any(
        is_tail_marker(blocks[index].text.strip())
        for index in range(first_article_index, article_indexes[-1])
    ):
        return _BodyTailResolution(
            is_valid=False, reason="tail_noise_inside_article_block"
        )

    article_after_tail_start = False
    last_reason: str | None = None
    for split_idx in range(len(article_indexes) - 1, -1, -1):
        candidate_last = article_indexes[split_idx]
        tail_result = _analyze_s3_tail(
            blocks,
            last_article_index=candidate_last,
        )
        if not tail_result.is_valid:
            last_reason = tail_result.reason
            continue
        later_articles = article_indexes[split_idx + 1 :]
        if later_articles and any(
            idx >= tail_result.tail_start for idx in later_articles
        ):
            article_after_tail_start = True
            continue
        return _BodyTailResolution(
            is_valid=True,
            first_article_index=first_article_index,
            last_article_index=candidate_last,
            body_end=tail_result.body_end,
            tail_start=tail_result.tail_start,
        )

    if article_after_tail_start:
        return _BodyTailResolution(
            is_valid=False, reason="s3_article_after_tail_start"
        )
    return _BodyTailResolution(
        is_valid=False, reason=last_reason or "s3_tail_signal_missing"
    )


@dataclass(frozen=True, slots=True)
class _TailResult:
    is_valid: bool
    reason: str | None = None
    body_end: int = -1
    tail_start: int | None = None


def _analyze_s3_tail(
    blocks: tuple[ExtractedBlock, ...],
    *,
    last_article_index: int,
) -> _TailResult:
    region_end = len(blocks)

    # 先尝试 S1 风格的简单尾部边界，确定正文结束位置
    tail_start, body_end, tail_ambiguous = find_tail_boundary(
        blocks,
        last_article_index=last_article_index,
        region_end=region_end,
    )

    # 如果 S1 发现尾部但尾部里没有 S3 强信号，则不是 S3
    if tail_start is not None and not tail_ambiguous:
        if not _has_s3_strong_signal(blocks, tail_start, region_end):
            return _TailResult(
                is_valid=False, reason="s3_tail_signal_missing"
            )
        # 在 S1 已确认的尾部范围内重新分类并校验
        classification = _classify_tail_region(
            blocks, tail_start=tail_start, region_end=region_end
        )
        if not classification.is_valid:
            return _TailResult(
                is_valid=False, reason=classification.reason
            )
        return _TailResult(
            is_valid=True,
            body_end=body_end,
            tail_start=tail_start,
        )

    # S1 未发现尾部或存在歧义：从正文后显式寻找 S3 强信号
    return _find_s3_tail_from_body_end(
        blocks,
        body_end=body_end,
        region_end=region_end,
    )


def _has_s3_strong_signal(
    blocks: tuple[ExtractedBlock, ...],
    start: int,
    end: int,
) -> bool:
    return any(
        _is_s3_strong_signal(blocks[index].text.strip())
        for index in range(start, end)
    )


def _find_s3_tail_from_body_end(
    blocks: tuple[ExtractedBlock, ...],
    *,
    body_end: int,
    region_end: int,
) -> _TailResult:
    strong_signal_index: int | None = None
    for index in range(body_end + 1, region_end):
        text = blocks[index].text.strip()
        if not text:
            continue
        if _is_s3_strong_signal(text):
            strong_signal_index = index
            break
        if is_tail_marker(text) or is_footer_line(text):
            continue
        return _TailResult(
            is_valid=False, reason="s3_unclassified_tail_block"
        )

    if strong_signal_index is None:
        return _TailResult(
            is_valid=False, reason="s3_tail_signal_missing"
        )

    # 向前吸收与强信号连续的印发信息、页脚和允许噪声
    tail_start = strong_signal_index
    for index in range(strong_signal_index - 1, body_end, -1):
        text = blocks[index].text.strip()
        if not text:
            tail_start = index
            continue
        if (
            is_tail_marker(text)
            or is_footer_line(text)
            or _is_print_metadata(text)
        ):
            tail_start = index
            continue
        break

    classification = _classify_tail_region(
        blocks, tail_start=tail_start, region_end=region_end
    )
    if not classification.is_valid:
        return _TailResult(is_valid=False, reason=classification.reason)

    return _TailResult(
        is_valid=True,
        body_end=body_end,
        tail_start=tail_start,
    )


def _is_s3_strong_signal(text: str) -> bool:
    return (
        bool(ATTACHMENT_HEADING_PATTERN.match(text))
        or bool(FORM_TEMPLATE_TITLE_PATTERN.match(text))
        or bool(SCORE_TABLE_PATTERN.search(text))
    )


def _is_print_metadata(text: str) -> bool:
    return bool(PRINT_METADATA_PATTERN.search(text))


@dataclass(frozen=True, slots=True)
class _TailClassification:
    is_valid: bool
    reason: str | None = None


def _classify_tail_region(
    blocks: tuple[ExtractedBlock, ...],
    *,
    tail_start: int,
    region_end: int,
) -> _TailClassification:
    attachment_heading_indexes = tuple(
        index
        for index in range(tail_start, region_end)
        if ATTACHMENT_HEADING_PATTERN.match(blocks[index].text.strip())
    )
    if len(attachment_heading_indexes) > 1:
        return _TailClassification(
            is_valid=False, reason="s3_tail_start_ambiguous"
        )

    for index in range(tail_start, region_end):
        text = blocks[index].text.strip()
        if not text:
            continue
        if ARTICLE_PATTERN.match(text):
            return _TailClassification(
                is_valid=False, reason="s3_article_after_tail_start"
            )
        kind = _classify_tail_block(text)
        if kind is None:
            return _TailClassification(
                is_valid=False, reason="s3_unclassified_tail_block"
            )
    return _TailClassification(is_valid=True)


def _classify_tail_block(text: str) -> str | None:
    if ATTACHMENT_HEADING_PATTERN.match(text):
        return "attachment_index"
    if FORM_TEMPLATE_TITLE_PATTERN.match(text):
        return "form_template"
    if SCORE_TABLE_PATTERN.search(text):
        return "score_table"
    if is_footer_line(text) or _is_print_metadata(text):
        return "trailing_print_metadata"
    if TEMPLATE_FIELD_PATTERN.search(text):
        return "form_template"
    if is_tail_marker(text):
        return "word_page_field"
    return None


def _build_s3_excluded_ranges(
    blocks: tuple[ExtractedBlock, ...],
    *,
    tail_start: int,
) -> tuple[ExcludedRange, ...]:
    ranges: list[ExcludedRange] = []
    current_kind: str | None = None
    current_start: int | None = None

    for index in range(tail_start, len(blocks)):
        text = blocks[index].text.strip()
        if not text:
            continue
        kind = _classify_tail_block(text)
        if kind is None:
            continue
        if kind != current_kind:
            if current_kind is not None and current_start is not None:
                ranges.append(
                    _make_excluded_range(blocks, current_start, index - 1, current_kind)
                )
            current_kind = kind
            current_start = index

    if current_kind is not None and current_start is not None:
        ranges.append(
            _make_excluded_range(
                blocks, current_start, len(blocks) - 1, current_kind
            )
        )

    return tuple(ranges)


def _make_excluded_range(
    blocks: tuple[ExtractedBlock, ...],
    start: int,
    end: int,
    kind: str,
) -> ExcludedRange:
    start_block = blocks[start]
    end_block = blocks[end]
    reason = {
        "trailing_print_metadata": "print_metadata_after_last_article",
        "attachment_index": "attachment_index_after_last_article",
        "form_template": "form_template_after_last_article",
        "score_table": "score_table_after_last_article",
        "word_page_field": "word_page_field_after_last_article",
    }[kind]
    return ExcludedRange(
        source_span=SourceSpan(
            start=start_block.location,
            end=end_block.location,
            start_char_offset=0,
            end_char_offset=len(end_block.text),
        ),
        kind=kind,
        reason=reason,
    )


def _find_s3_title(
    blocks: tuple[ExtractedBlock, ...],
    expected_title: str,
) -> int | None:
    normalized_expected = normalize_title(expected_title)
    exact_indexes = tuple(
        index
        for index, block in enumerate(blocks)
        if normalize_title(block.text) == normalized_expected
    )
    if len(exact_indexes) == 1:
        return exact_indexes[0]
    if len(exact_indexes) > 1:
        return None

    # 模糊匹配：限制在第一个条文之前，避免命中正文引用
    candidates: list[tuple[int, float]] = []
    for index, block in enumerate(blocks):
        text = block.text.strip()
        if not text:
            continue
        if index > 0 and ARTICLE_PATTERN.match(text):
            break
        ratio = SequenceMatcher(
            None, normalize_title(text), normalized_expected
        ).ratio()
        if ratio >= TITLE_FUZZY_THRESHOLD:
            candidates.append((index, ratio))

    if len(candidates) == 1:
        return candidates[0][0]
    return None


def _s3_review(
    extraction: ExtractionResult,
    *,
    source: SourceRef,
    expected_title: str,
    reason: str,
) -> LegalDocumentIntermediate:
    return _s3_blocked_intermediate(
        extraction,
        source=source,
        expected_title=expected_title,
        status="review_required",
        reason=reason,
    )


def _s3_blocked_intermediate(
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
        content_class=ContentClass.S3,
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
