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
from app.services.legal_content_boundary import (
    S1BoundaryStrategy,
    identify_s1_target_body,
)
from app.services.legal_intermediate import validate_legal_intermediate


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


def _extraction(source: SourceRef, lines, *, extractor_kind="W"):
    blocks = tuple(
        ExtractedBlock(
            order=order,
            text=line,
            location=SourceLocation(
                logical_page=1,
                page_number=None,
                block_order=order,
                line_number=order + 1,
            ),
        )
        for order, line in enumerate(lines)
    )
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


def test_s1_boundary_confirms_unique_title_continuous_articles_and_tail_noise(
    tmp_path,
):
    source = _source(tmp_path)
    extraction = _extraction(
        source,
        (
            "某规定",
            "第一章 总则",
            "第一条 正文",
            "续行正文。",
            "第二条 末条正文。",
            "",
            "某机关办公室。",
            "某机关 2026年6月29日印发",
            "PAGE \\* MERGEFORMAT",
        ),
    )

    intermediate = identify_s1_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text == (
        "某规定\n第一章 总则\n第一条 正文\n续行正文。\n第二条 末条正文。"
    )
    assert [unit.kind for unit in intermediate.body_units] == [
        "title",
        "chapter",
        "article",
        "paragraph",
        "article",
    ]
    assert len(intermediate.extraction_report.excluded_ranges) == 1
    assert "办公室" not in intermediate.body_text
    assert "印发" not in intermediate.body_text
    assert "PAGE" not in intermediate.body_text
    validate_legal_intermediate(intermediate)


def test_s1_boundary_keeps_printing_word_inside_article_body(tmp_path):
    source = _source(tmp_path)
    extraction = _extraction(
        source,
        (
            "某规定",
            "第一条 根据某办公厅印发的工作意见，结合实际制定本规定。",
            "第二条 本规定自印发之日起施行。",
        ),
    )

    intermediate = identify_s1_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert "办公厅印发的工作意见" in intermediate.body_text


def test_s1_boundary_excludes_copy_distribution_footer_after_blank(tmp_path):
    source = _source(tmp_path)
    extraction = _extraction(
        source,
        (
            "某规定",
            "第一条 正文。",
            "",
            "抄送：某上级机关，某有关单位。",
            "某机关办公室 2026年6月29日印发",
            "承办单位：法制处  经办人：某某",
        ),
    )

    intermediate = identify_s1_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text == "某规定\n第一条 正文。"
    assert len(intermediate.extraction_report.excluded_ranges) == 1


@pytest.mark.parametrize(
    ("lines", "expected_ambiguity"),
    [
        (("某规定", "某规定", "第一条 正文"), "title_not_unique"),
        (("某规定", "第二条 正文"), "first_article_missing"),
        (
            ("某规定", "第一条 正文", "第三条 正文"),
            "article_sequence_broken",
        ),
        (
            ("某规定", "第一条 正文", "", "无法分类的普通尾部文本"),
            "trailing_content_ambiguous",
        ),
        (
            (
                "某规定",
                "第一条 正文",
                "",
                "本规定由某办公厅负责解释。",
            ),
            "trailing_content_ambiguous",
        ),
    ],
)
def test_s1_boundary_routes_ambiguous_evidence_to_review(
    tmp_path,
    lines,
    expected_ambiguity,
):
    source = _source(tmp_path)

    intermediate = identify_s1_target_body(
        _extraction(source, lines),
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "review_required"
    assert expected_ambiguity in intermediate.boundary.ambiguities
    assert intermediate.body_text == ""
    assert intermediate.body_units == ()


def test_s1_strategy_does_not_require_word_extraction_axis(tmp_path):
    source = _source(tmp_path)
    extraction = _extraction(
        source,
        ("某规定", "第一条 正文"),
        extractor_kind="PT",
    )

    intermediate = S1BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title="某规定",
    )

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.extraction_class.value == "PT"
