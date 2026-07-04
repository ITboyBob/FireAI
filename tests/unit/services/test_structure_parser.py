from pathlib import Path
import json

import pytest

from app.services.legal_content_boundary import identify_s1_target_body
from app.services.legal_s2_boundary import S2BoundaryStrategy
from app.services.legal_s3_boundary import S3BoundaryStrategy
from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import IngestionDisposition, SourceRef
from app.services.structure_parser import (
    parse_legal_document,
    parse_legal_intermediate,
    write_structured_document,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "structured"


def _confirmed_intermediate(tmp_path: Path):
    source_path = tmp_path / "某规定.doc"
    source_path.write_bytes(b"sample")
    from hashlib import sha256

    source = SourceRef(
        relative_path="某规定.doc",
        source_path=source_path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )
    lines = (
        "某规定",
        "第一章 总则",
        "第一条 第一款正文。",
        "第二款正文。",
        "第二条 第二条正文。",
    )
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
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
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
    )
    return identify_s1_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )


def _s2_intermediate(tmp_path: Path):
    source_path = tmp_path / "某规定.doc"
    source_path.write_bytes(b"sample")
    from hashlib import sha256

    source = SourceRef(
        relative_path="某规定.doc",
        source_path=source_path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )
    lines = (
        "某省人民政府",
        "关于修订《某规定》的决定",
        "某规定",
        "（2020年1月1日公布）",
        "第一章 总则",
        "第一条 第一款正文。",
        "第二款正文。",
        "第二章 分则",
        "第二条 第二条正文。",
    )
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
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
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
    )
    return S2BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title="某规定",
    )


def _s3_intermediate(tmp_path: Path):
    source_path = tmp_path / "某规定.doc"
    source_path.write_bytes(b"sample")
    from hashlib import sha256

    source = SourceRef(
        relative_path="某规定.doc",
        source_path=source_path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )
    lines = (
        "某规定",
        "第一条 第一款正文。",
        "第二款正文。",
        "第二条 第二条正文。",
        "",
        "某机关 2026年6月29日印发",
        "",
        "附件：",
        "",
        "行政执法监督文书1：",
        "审批表",
        "姓名：",
        "单位：",
    )
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
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
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
    )
    return S3BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title="某规定",
    )


def test_parse_legal_document_extracts_article_and_chapter():
    raw = (FIXTURE_DIR / "fire_law_fragment.txt").read_text(encoding="utf-8")

    document = parse_legal_document("xiaofangfa_2019", raw)

    assert document.document_id == "xiaofangfa_2019"
    assert document.title == "中华人民共和国消防法"
    assert document.region == "全国"
    assert document.effective_on == "2009年5月1日"
    assert document.articles[0].article_no == "第二条"
    assert document.articles[0].chapter_title == "第一章 总则"
    assert document.articles[0].heading_path == ("第一章 总则",)
    assert document.articles[0].text == (
        "国家实行消防安全责任制。\n"
        "各级人民政府应当将消防工作纳入国民经济和社会发展计划。"
    )


def test_parse_legal_document_prefers_actual_law_title_over_preface():
    raw = (
        "河北省人民政府令\n"
        "〔2019〕第11号\n"
        "《河北省人民政府关于废止和修改部分省政府规章的决定》已经2019年12月15日省政府第73次常务会议通过，自公布之日起施行。\n"
        "2019年12月28日\n"
        "河北省人民政府\n"
        "关于废止和修改部分省政府规章的决定\n"
        "第五条 第一款第一项中的“公安部门”修改为“应急管理部门”。\n"
        "第六条 中的“公安机关消防机构”修改为“消防救援机构”。\n"
        "河北省消防安全责任制实施办法\n"
        "（2009年10月29日河北省人民政府令〔2009〕第8号公布 根据2014年1月16日河北省人民政府令〔2014〕第2号第一次修正 "
        "根据2019年12月28日河北省人民政府令〔2019〕第11号第二次修正）\n"
        "第一章 总则\n"
        "第一条 为明确和落实消防安全责任，制定本办法。\n"
        "第二十四条 本办法自2009年12月1日起施行。\n"
    )

    document = parse_legal_document(
        "hebei_xiaofang_anquan_zerenzhi_shishi_banfa",
        raw,
    )

    assert document.title == "河北省消防安全责任制实施办法"
    assert document.issuing_authority == "河北省人民政府"
    assert document.region == "河北省"
    assert document.promulgated_on == "2009年10月29日"
    assert document.effective_on == "2009年12月1日"
    assert document.articles[0].article_no == "第一条"
    assert document.articles[0].text == "为明确和落实消防安全责任，制定本办法。"


def test_write_structured_document_persists_structured_json(tmp_path: Path):
    raw = (FIXTURE_DIR / "fire_law_fragment.txt").read_text(encoding="utf-8")
    document = parse_legal_document("xiaofangfa_2019", raw)

    output_path = write_structured_document(document, tmp_path / "data" / "structured")

    assert output_path == tmp_path / "data" / "structured" / "xiaofangfa_2019.json"

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["document_id"] == "xiaofangfa_2019"
    assert payload["title"] == "中华人民共和国消防法"
    assert payload["articles"][0]["heading_path"] == ["第一章 总则"]
    assert payload["articles"][0]["article_no"] == "第二条"


def test_parse_legal_document_extracts_spaced_dates_from_parenthetical():
    raw = (
        "机关、团体、企业、事业单位消防安全管理规定\n"
        "（2001 年 11 月 14 日公安部令第 61 号公布 自 2002 年 5 月 1 日起施行）\n"
        "第一章 总则\n"
        "第一条 为了加强和规范单位消防安全管理，制定本规定。\n"
    )

    document = parse_legal_document(
        "jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding",
        raw,
    )

    assert document.promulgated_on == "2001年11月14日"
    assert document.effective_on == "2002年5月1日"


def test_parse_legal_document_keeps_real_article_after_inline_hyperlink_cleanup():
    raw = (FIXTURE_DIR / "xiaofangfa_article_62_clean.txt").read_text(encoding="utf-8")

    document = parse_legal_document("xiaofangfa_2019", raw)

    assert document.title == "中华人民共和国消防法"
    assert document.articles[0].article_no == "第六十二条"
    assert document.articles[0].text.startswith(
        "有下列行为之一的，依照《中华人民共和国治安管理处罚法》的规定处罚："
    )


def test_parse_legal_intermediate_binds_confirmed_source_metadata_and_spans(
    tmp_path,
):
    intermediate = _confirmed_intermediate(tmp_path)

    document = parse_legal_intermediate(intermediate)

    assert document.document_id == intermediate.document_id
    assert document.title == "某规定"
    assert document.source_sha256 == intermediate.source_ref.source_sha256
    assert document.extraction_class == "W"
    assert document.content_class == "S1"
    assert document.boundary_status == "confirmed"
    assert document.articles[0].article_no == "第一条"
    assert document.articles[0].text == "第一款正文。\n第二款正文。"
    assert document.articles[0].source_span.start.block_order == 2
    assert document.articles[0].source_span.end.block_order == 3
    assert document.articles[1].source_span.start.block_order == 4


def test_parse_legal_intermediate_rejects_non_confirmed_before_parser(
    tmp_path,
    monkeypatch,
):
    intermediate = _confirmed_intermediate(tmp_path)
    ambiguous = identify_s1_target_body(
        ExtractionResult(
            source_sha256=intermediate.source_ref.source_sha256,
            extractor_kind="W",
            extractor_version="fake-v1",
            pages=(
                ExtractedPage(
                    logical_page=1,
                    page_number=None,
                    block_orders=(0, 1, 2),
                ),
            ),
            text_blocks=(
                ExtractedBlock(
                    order=0,
                    text="某规定",
                    location=SourceLocation(
                        logical_page=1,
                        page_number=None,
                        block_order=0,
                        line_number=1,
                    ),
                ),
                ExtractedBlock(
                    order=1,
                    text="某规定",
                    location=SourceLocation(
                        logical_page=1,
                        page_number=None,
                        block_order=1,
                        line_number=2,
                    ),
                ),
                ExtractedBlock(
                    order=2,
                    text="第一条 正文",
                    location=SourceLocation(
                        logical_page=1,
                        page_number=None,
                        block_order=2,
                        line_number=3,
                    ),
                ),
            ),
            disposition=IngestionDisposition.READY,
        ),
        source=intermediate.source_ref,
        expected_title="某规定",
    )
    calls = []
    monkeypatch.setattr(
        "app.services.structure_parser.parse_legal_document",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="confirmed"):
        parse_legal_intermediate(ambiguous)

    assert calls == []


def test_parse_legal_intermediate_prefers_target_metadata_for_s2(tmp_path):
    intermediate = _s2_intermediate(tmp_path)

    document = parse_legal_intermediate(intermediate)

    assert document.issuing_authority == "某省人民政府"
    assert document.promulgated_on == "2020年1月1日"
    assert document.revision_events == (
        "关于修订《某规定》的决定",
    )
    assert document.metadata_evidence == intermediate.target.evidence
    assert any(
        ev.field_name == "issuing_authority"
        and ev.extraction_status == "confirmed"
        for ev in document.metadata_evidence
    )


def test_parse_legal_intermediate_keeps_parsed_metadata_when_target_empty(
    tmp_path,
):
    intermediate = _confirmed_intermediate(tmp_path)

    document = parse_legal_intermediate(intermediate)

    assert document.issuing_authority is None
    assert document.promulgated_on is None
    assert document.revision_events == ()
    assert document.metadata_evidence == ()
    assert document.version_basis is None


def test_parse_legal_intermediate_binds_s3_confirmed_source_contract_and_spans(
    tmp_path,
):
    intermediate = _s3_intermediate(tmp_path)

    document = parse_legal_intermediate(intermediate)

    assert document.document_id == intermediate.document_id
    assert document.title == "某规定"
    assert document.source_sha256 == intermediate.source_ref.source_sha256
    assert document.extraction_class == "W"
    assert document.content_class == "S3"
    assert document.boundary_status == "confirmed"
    assert len(document.articles) == 2
    assert document.articles[0].article_no == "第一条"
    assert document.articles[0].text == "第一款正文。\n第二款正文。"
    assert document.articles[1].article_no == "第二条"
    assert document.articles[1].text == "第二条正文。"
    assert all(article.source_span is not None for article in document.articles)
