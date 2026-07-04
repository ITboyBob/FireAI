from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import IngestionDisposition, SourceRef
from app.services.legal_intermediate import validate_legal_intermediate
from app.services.legal_s3_boundary import S3BoundaryStrategy, identify_s3_target_body


def _source(tmp_path: Path, title="某规定") -> SourceRef:
    path = tmp_path / f"{title}.doc"
    path.write_bytes(b"sample")
    return SourceRef(
        relative_path=path.name,
        source_path=path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )


def _location(order: int) -> SourceLocation:
    return SourceLocation(
        logical_page=1,
        page_number=None,
        block_order=order,
        line_number=order + 1,
    )


def _block(order: int, text: str) -> ExtractedBlock:
    return ExtractedBlock(
        order=order,
        text=text,
        location=_location(order),
    )


def _extraction(source: SourceRef, lines, *, extractor_kind="W") -> ExtractionResult:
    blocks = tuple(_block(order, line) for order, line in enumerate(lines))
    return ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind=extractor_kind,
        extractor_version="fake-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=tuple(range(len(blocks))),
            ),
        ),
        text_blocks=blocks,
        disposition=IngestionDisposition.READY,
        warnings=("physical_pagination_unknown",),
    )


def test_s3_confirms_unique_title_continuous_articles_and_tail_materials(
    tmp_path,
):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条正文。",
        "",
        "某机关办公室",
        "某机关 2026年6月29日印发",
        "",
        "附件：",
        "",
        "行政执法监督文书1：",
        "审批表",
        "姓名：",
        "单位：",
        "",
        "PAGE \\* MERGEFORMAT",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text.startswith("某规定")
    assert "某机关办公室" not in intermediate.body_text
    assert "附件" not in intermediate.body_text
    assert "审批表" not in intermediate.body_text
    assert "PAGE" not in intermediate.body_text
    assert len(intermediate.body_units) == 3
    kinds = [unit.kind for unit in intermediate.body_units]
    assert kinds == ["title", "article", "article"]
    excluded = intermediate.extraction_report.excluded_ranges
    assert len(excluded) >= 2
    assert all(
        er.kind in {
            "trailing_print_metadata",
            "attachment_index",
            "form_template",
            "word_page_field",
        }
        for er in excluded
    )
    validate_legal_intermediate(intermediate)


def test_s3_tail_start_absorbs_print_metadata_before_attachment(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "某机关 2026年6月29日印发",
        "承办单位：某处",
        "",
        "附件：",
        "1. 审批表",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert "某机关 2026年6月29日印发" not in intermediate.body_text
    assert "承办单位" not in intermediate.body_text
    excluded = intermediate.extraction_report.excluded_ranges
    assert excluded
    first_excluded = excluded[0]
    assert first_excluded.kind == "trailing_print_metadata"
    assert first_excluded.source_span.start.block_order <= 4
    validate_legal_intermediate(intermediate)


def test_s3_does_not_truncate_body_when_attachment_mentioned_inside_article(
    tmp_path,
):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 根据《某审批表》和《某决定书》制定本规定。",
        "第二条 末条。",
        "",
        "某机关办公室",
        "某机关 2026年6月29日印发",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    # 仅有印发信息不足以触发 S3，策略应要求人工复核
    assert intermediate.boundary.status == "review_required"
    assert "s3_tail_signal_missing" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""
    assert intermediate.body_units == ()


def test_s3_does_not_truncate_when_attachment_heading_appears_before_title(
    tmp_path,
):
    source = _source(tmp_path, title="某规定")
    lines = (
        "附件：",
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "附件：",
        "1. 审批表",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert "附件" not in intermediate.body_text
    assert len(intermediate.body_units) == 3
    validate_legal_intermediate(intermediate)


def test_s3_confirms_form_template_series_without_attachment_heading(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "行政执法监督文书1：",
        "审批表",
        "姓名：",
        "单位：",
        "",
        "行政执法监督文书2：",
        "意见书",
        "意见：",
        "签名：",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert "行政执法监督文书" not in intermediate.body_text
    assert "审批表" not in intermediate.body_text
    assert "意见书" not in intermediate.body_text
    excluded = intermediate.extraction_report.excluded_ranges
    assert any(er.kind == "form_template" for er in excluded)
    validate_legal_intermediate(intermediate)


def test_s3_reviews_when_no_strong_tail_signal(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "某机关 2026年6月29日印发",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "s3_tail_signal_missing" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""
    assert intermediate.body_units == ()


def test_s3_reviews_when_unclassified_tail_block(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "附件：",
        "1. 审批表",
        "",
        "无法解释的普通说明文字",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "s3_unclassified_tail_block" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""


def test_s3_reviews_when_article_reappears_after_tail_start(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "附件：",
        "1. 审批表",
        "",
        "第三条 不应出现的条文。",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "s3_article_after_tail_start" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""


def test_s3_reviews_when_multiple_tail_starts_are_equally_valid(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "附件：",
        "",
        "附件：",
        "1. 审批表",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "s3_tail_start_ambiguous" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""


def test_s3_reviews_when_article_sequence_broken(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第三条 正文。",
        "",
        "附件：",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "s3_article_sequence_broken" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""


def test_s3_rejects_when_block_order_invalid(tmp_path):
    source = _source(tmp_path, title="某规定")
    blocks = (
        _block(0, "某规定"),
        _block(2, "第一条 正文。"),
    )
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=(0, 2),
            ),
        ),
        text_blocks=blocks,
        disposition=IngestionDisposition.READY,
        warnings=("physical_pagination_unknown",),
    )

    intermediate = identify_s3_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "rejected"
    assert "block_order_invalid" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""


def test_s3_rejects_when_digest_mismatch(tmp_path):
    source = _source(tmp_path, title="某规定")
    extraction = _extraction(source, ("某规定", "第一条 正文。"))
    extraction = ExtractionResult(
        source_sha256="mismatch",
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=extraction.pages,
        text_blocks=extraction.text_blocks,
        disposition=IngestionDisposition.READY,
        warnings=extraction.warnings,
    )

    intermediate = identify_s3_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "rejected"
    assert "source_digest_mismatch" in intermediate.boundary.ambiguities


def test_s3_rejects_when_extraction_not_ready(tmp_path):
    source = _source(tmp_path, title="某规定")
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(),
        text_blocks=(),
        disposition=IngestionDisposition.FAILED,
        failure=object(),  # type: ignore[arg-type]
    )

    intermediate = identify_s3_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "rejected"
    assert "extraction_not_ready" in intermediate.boundary.ambiguities


def test_s3_excluded_ranges_are_strictly_after_body_and_non_overlapping(
    tmp_path,
):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一章 总则",
        "第一条 正文。",
        "续行。",
        "第二条 末条。",
        "",
        "某机关 2026年6月29日印发",
        "",
        "附件：",
        "文书1：",
        "字段",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    body_end = intermediate.body_units[-1].source_span.end.block_order
    excluded = intermediate.extraction_report.excluded_ranges
    assert excluded
    prev_end = -1
    for er in excluded:
        assert er.source_span.start.block_order > body_end
        assert er.source_span.start.block_order > prev_end
        prev_end = er.source_span.end.block_order
    validate_legal_intermediate(intermediate)


def test_s3_blocked_intermediate_has_empty_body_and_units(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第三条 正文。",
        "",
        "附件：",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert intermediate.body_text == ""
    assert intermediate.body_units == ()
    assert not intermediate.extraction_report.excluded_ranges


def test_s3_fuzzy_title_match_when_filename_differs_by_minor_insertion(
    tmp_path,
):
    source = _source(tmp_path, title="河北省消防救援机构执法过错责任追究规定")
    lines = (
        "河北省消防救援机构行政执法过错责任追究规定",
        "第一条 正文。",
        "第二条 末条。",
        "",
        "附件：",
        "文书1：",
    )

    intermediate = identify_s3_target_body(
        _extraction(source, lines),
        source=source,
        expected_title=source.source_path.stem,
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text.startswith("河北省消防救援机构")
    assert "附件" not in intermediate.body_text
    validate_legal_intermediate(intermediate)


def test_s3_strategy_class_exposes_kind_and_version(tmp_path):
    source = _source(tmp_path, title="某规定")
    strategy = S3BoundaryStrategy()
    extraction = _extraction(
        source,
        ("某规定", "第一条 正文。", "第二条 末条。", "", "附件：", "1. 审批表"),
    )

    intermediate = strategy.identify(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert strategy.kind == "S3"
    assert strategy.version
    assert intermediate.boundary.status == "confirmed"
