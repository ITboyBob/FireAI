from pathlib import Path
import json

from app.services.structure_parser import parse_legal_document, write_structured_document


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "structured"


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
