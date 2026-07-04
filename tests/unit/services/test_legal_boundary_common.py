import pytest

from app.services.legal_boundary_common import (
    ARTICLE_PATTERN,
    HEADING_PATTERN,
    article_number,
    body_unit,
    build_body_units,
    chinese_number_to_int,
    find_tail_boundary,
    is_footer_line,
    is_tail_marker,
    normalize_title,
)
from app.services.legal_extractor import ExtractedBlock, SourceLocation
from app.services.legal_intermediate import BodyUnit


def _block(text: str, order: int = 0) -> ExtractedBlock:
    return ExtractedBlock(
        order=order,
        text=text,
        location=SourceLocation(
            logical_page=1,
            page_number=1,
            block_order=order,
            line_number=1,
        ),
    )


class TestNormalizeTitle:
    def test_removes_whitespace_and_brackets(self):
        assert normalize_title(" 《 河北 消防 规定 》 ") == "河北消防规定"

    def test_normalizes_fullwidth(self):
        assert normalize_title("《河北消防规定》") == "河北消防规定"


class TestChineseNumberToInt:
    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("一", 1),
            ("十", 10),
            ("十一", 11),
            ("二十三", 23),
            ("一百零一", 101),
            ("二十九", 29),
            ("两", 2),
            ("〇", 0),
            ("10", 10),
        ],
    )
    def test_conversions(self, input_value, expected):
        assert chinese_number_to_int(input_value) == expected

    def test_invalid_character_raises(self):
        with pytest.raises(KeyError):
            chinese_number_to_int("xyz")


class TestArticleNumber:
    def test_extracts_chinese_article_number(self):
        block = _block("第一条  为规范...")
        assert article_number(block) == 1

    def test_extracts_arabic_article_number(self):
        block = _block("第10条  为规范...")
        assert article_number(block) == 10

    def test_non_article_raises(self):
        with pytest.raises(ValueError):
            article_number(_block("本规定自发布之日起施行。"))


class TestPatterns:
    def test_article_pattern_matches_chinese(self):
        match = ARTICLE_PATTERN.match("第一条  为规范...")
        assert match is not None
        assert match.group(1) == "一"

    def test_heading_pattern_matches_chapter(self):
        match = HEADING_PATTERN.match("第一章  总则")
        assert match is not None
        assert match.group(1) == "章"


class TestBodyUnit:
    def test_builds_unit_with_parent(self):
        block = _block("第一款内容", order=5)
        unit = body_unit(
            block=block,
            unit_id="unit-3",
            kind="paragraph",
            text="第一款内容",
            parent_unit_id="unit-2",
        )
        assert isinstance(unit, BodyUnit)
        assert unit.unit_id == "unit-3"
        assert unit.parent_unit_id == "unit-2"


class TestBuildBodyUnits:
    def test_builds_title_and_articles(self):
        blocks = (
            _block("河北省消防救援机构执法过错责任追究规定", order=0),
            _block("第一章  总则", order=1),
            _block("第一条  为规范...", order=2),
            _block("本条第二款说明。", order=3),
            _block("第二条  为进一步...", order=4),
        )
        units = build_body_units(
            blocks,
            title_index=0,
            first_article_index=1,
            body_end=len(blocks) - 1,
            expected_title="河北省消防救援机构执法过错责任追究规定",
        )
        assert len(units) == 5
        assert units[0].kind == "title"
        assert units[0].unit_id == "unit-0"
        assert units[1].kind == "chapter"
        assert units[2].kind == "article"
        assert units[3].kind == "paragraph"
        assert units[3].parent_unit_id == units[2].unit_id


class TestTailMarkers:
    @pytest.mark.parametrize(
        "text",
        [
            "PAGE \\* MERGEFORMAT",
            "第 1 页",
            "第  5  页",
            "2024年1月1日印发",
            "2024年 1 月 1 日 印发。",
        ],
    )
    def test_tail_markers_recognized(self, text):
        assert is_tail_marker(text) is True

    def test_plain_text_not_tail_marker(self):
        assert is_tail_marker("正文内容") is False


class TestFooterLine:
    @pytest.mark.parametrize(
        "text",
        [
            "抄送：各支队。",
            "河北省消防救援总队办公室。",
            "某省人民政府规章。",
        ],
    )
    def test_footer_lines_recognized(self, text):
        assert is_footer_line(text) is True

    def test_article_text_not_footer(self):
        assert is_footer_line("第一条  为规范...") is False


class TestFindTailBoundary:
    def test_finds_page_field_tail(self):
        blocks = (
            _block("第二十九条  本规定自发布之日起施行。", order=0),
            _block("", order=1),
            _block("河北省消防救援总队办公室。", order=2),
            _block("PAGE \\* MERGEFORMAT", order=3),
        )
        tail_start, body_end, ambiguous = find_tail_boundary(
            blocks, last_article_index=0
        )
        assert tail_start == 2
        assert body_end == 0
        assert ambiguous is False

    def test_extends_body_before_blank_tail(self):
        blocks = (
            _block("第二十八条  ...", order=0),
            _block("第二十九条  本规定自发布之日起施行。", order=1),
            _block("", order=2),
            _block("附则说明", order=3),
        )
        tail_start, body_end, ambiguous = find_tail_boundary(
            blocks, last_article_index=1
        )
        assert tail_start is None
        assert body_end == 1
        assert ambiguous is True

    def test_no_tail_signal_returns_none(self):
        blocks = (
            _block("第二十九条  ...", order=0),
            _block("", order=1),
            _block("", order=2),
        )
        tail_start, body_end, ambiguous = find_tail_boundary(
            blocks, last_article_index=0
        )
        assert tail_start is None
        assert body_end == 0
        assert ambiguous is False

    def test_region_end_limits_search(self):
        blocks = (
            _block("第二十九条  ...", order=0),
            _block("河北省消防救援总队办公室。", order=1),
            _block("PAGE \\* MERGEFORMAT", order=2),
            _block("未知内容", order=3),
        )
        tail_start, body_end, ambiguous = find_tail_boundary(
            blocks, last_article_index=0, region_end=3
        )
        assert tail_start == 2
        assert body_end == 1
        assert ambiguous is False
