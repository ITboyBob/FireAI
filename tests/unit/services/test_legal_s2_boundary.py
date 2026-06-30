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
from app.services.legal_s2_boundary import S2BoundaryStrategy, identify_s2_target_body


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


def test_s2_confirms_unique_title_with_leading_publication_material(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某省人民政府令",
        "（2020）第1号",
        "《某规定》已经省政府通过，自公布之日起施行。",
        "省长：某",
        "2020年1月1日",
        "",
        "某规定",
        "",
        "第一章 总则",
        "第一条 正文。",
        "第二条 末条。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text.startswith("某规定")
    assert "某省人民政府令" not in intermediate.body_text
    assert "省长" not in intermediate.body_text
    assert len(intermediate.extraction_report.excluded_ranges) == 1
    assert intermediate.extraction_report.excluded_ranges[0].kind == "leading_publication_material"
    validate_legal_intermediate(intermediate)


def test_s2_excludes_attachment2_before_title_without_truncating_body(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "附件2",
        "某机关决定修改的规章",
        "（摘录）",
        "十四、将《某规定》第一条修改为……",
        "",
        "某规定",
        "第一条 正文。",
        "第二条 末条。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert "附件2" not in intermediate.body_text
    assert "十四、将" not in intermediate.body_text
    assert "某规定" in intermediate.body_text
    assert any(
        excluded.kind == "leading_publication_material"
        for excluded in intermediate.extraction_report.excluded_ranges
    )
    validate_legal_intermediate(intermediate)


def test_s2_revision_decision_articles_do_not_count_as_target_body(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某机关关于修改部分规章的决定",
        "第一条中的‘应当’修改为‘可以’。",
        "第二条改为第三条。",
        "",
        "某规定",
        "第一条 正文。",
        "第二条 正文。",
        "第三条 末条。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    article_units = [
        unit for unit in intermediate.body_units if unit.kind == "article"
    ]
    assert len(article_units) == 3
    validate_legal_intermediate(intermediate)


def test_s2_selects_second_title_when_first_is_only_publication_header(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "某部、某委令",
        "（第1号）",
        "本规定自发布之日起施行。",
        "",
        "某规定",
        "第一章 总则",
        "第一条 正文。",
        "第二条 末条。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text.startswith("某规定")
    leading = intermediate.extraction_report.excluded_ranges[0]
    assert leading.source_span.end.block_order < intermediate.body_units[0].source_span.start.block_order
    validate_legal_intermediate(intermediate)


def test_s2_returns_review_when_two_candidates_have_full_articles(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某规定",
        "第一条 正文。",
        "第二条 正文。",
        "",
        "某规定",
        "第一条 其他。",
        "第二条 其他。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "title_candidate_ambiguous" in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""
    assert intermediate.body_units == ()


def test_s2_rejects_extraction_not_ready(tmp_path):
    source = _source(tmp_path)
    extraction = _extraction(source, ("某规定", "第一条 正文。"))
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(),
        text_blocks=(),
        disposition=IngestionDisposition.FAILED,
        failure=object(),  # type: ignore[arg-type]
    )

    intermediate = identify_s2_target_body(extraction, source=source, expected_title="某规定")

    assert intermediate.boundary.status == "rejected"
    assert intermediate.body_text == ""


def test_s2_rejects_digest_mismatch(tmp_path):
    source = _source(tmp_path)
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

    intermediate = identify_s2_target_body(extraction, source=source, expected_title="某规定")

    assert intermediate.boundary.status == "rejected"
    assert "source_digest_mismatch" in intermediate.boundary.ambiguities


def test_s2_rejects_invalid_block_order(tmp_path):
    source = _source(tmp_path)
    blocks = (
        ExtractedBlock(order=0, text="某规定", location=_location(0)),
        ExtractedBlock(order=2, text="第一条 正文。", location=_location(2)),
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

    intermediate = identify_s2_target_body(extraction, source=source, expected_title="某规定")

    assert intermediate.boundary.status == "rejected"
    assert "block_order_invalid" in intermediate.boundary.ambiguities


def test_s2_reviews_when_first_article_missing(tmp_path):
    source = _source(tmp_path)
    lines = (
        "前言",
        "某规定",
        "第二条 正文。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "first_article_missing" in intermediate.boundary.ambiguities


def test_s2_reviews_when_article_sequence_broken(tmp_path):
    source = _source(tmp_path)
    lines = (
        "某规定",
        "第一条 正文。",
        "第三条 正文。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert "article_sequence_broken" in intermediate.boundary.ambiguities


def test_s2_metadata_evidence_spans_point_to_extraction_blocks(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某省人民政府",
        "某规定",
        "（2020年1月1日公布）",
        "第一条 正文。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    evidence_fields = {ev.field_name: ev for ev in intermediate.target.evidence}
    assert "issuing_authority" in evidence_fields
    assert evidence_fields["issuing_authority"].extraction_status == "confirmed"
    assert evidence_fields["issuing_authority"].source_span.start.block_order == 0
    assert "promulgated_on" in evidence_fields
    validate_legal_intermediate(intermediate)


def test_s2_leading_excluded_range_does_not_overlap_body(tmp_path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某省人民政府令",
        "某规定",
        "第一条 正文。",
    )

    intermediate = identify_s2_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    excluded = intermediate.extraction_report.excluded_ranges[0].source_span
    body_start = intermediate.body_units[0].source_span.start.block_order
    assert excluded.end.block_order < body_start


def test_s2_strategy_class_exposes_kind_and_version(tmp_path):
    source = _source(tmp_path, title="某规定")
    strategy = S2BoundaryStrategy()
    extraction = _extraction(
        source,
        ("某规定", "第一条 正文。"),
    )

    intermediate = strategy.identify(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert strategy.kind == "S2"
    assert strategy.version
    assert intermediate.boundary.status == "confirmed"
