from pathlib import Path
import json

from app.services.chunk_builder import build_chunks, write_chunks


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "chunks"


def test_build_chunks_preserves_article_path_and_metadata():
    structured = {
        "document_id": "xiaofangfa_2019",
        "title": "中华人民共和国消防法",
        "issuing_authority": None,
        "region": "全国",
        "promulgated_on": None,
        "effective_on": "2009年5月1日",
        "articles": [
            {
                "article_no": "第二条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "国家实行消防安全责任制。",
            }
        ],
    }

    chunks = build_chunks(structured)

    assert chunks == [
        {
            "chunk_id": "xiaofangfa_2019#article-1",
            "document_id": "xiaofangfa_2019",
            "title": "中华人民共和国消防法",
            "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
            "article_index": 1,
            "chapter_title": "第一章 总则",
            "heading_path": ["第一章 总则"],
            "issuing_authority": None,
            "region": "全国",
            "promulgated_on": None,
            "effective_on": "2009年5月1日",
            "chunk_index": 1,
            "chunk_total": 1,
        }
    ]


def test_build_chunks_splits_long_article_by_paragraph_without_losing_path():
    structured = {
        "document_id": "hebei_xiaofang_tiaoli",
        "title": "河北省消防条例",
        "issuing_authority": None,
        "region": "河北省",
        "promulgated_on": None,
        "effective_on": "2010年7月1日",
        "articles": [
            {
                "article_no": "第一条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "第一段说明。\n第二段说明。\n第三段说明。",
            }
        ],
    }

    chunks = build_chunks(structured, max_chunk_chars=8)

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "hebei_xiaofang_tiaoli#article-1-part-1",
        "hebei_xiaofang_tiaoli#article-1-part-2",
        "hebei_xiaofang_tiaoli#article-1-part-3",
    ]
    assert [chunk["path"] for chunk in chunks] == [
        "河北省消防条例 > 第一章 总则 > 第一条",
        "河北省消防条例 > 第一章 总则 > 第一条",
        "河北省消防条例 > 第一章 总则 > 第一条",
    ]
    assert [chunk["text"] for chunk in chunks] == [
        "第一段说明。",
        "第二段说明。",
        "第三段说明。",
    ]
    assert [chunk["chunk_total"] for chunk in chunks] == [3, 3, 3]


def test_build_chunks_omits_missing_heading_from_path():
    structured = {
        "document_id": "hebei_xiaofang_anquan_zerenzhi_shishi_banfa",
        "title": "河北省消防安全责任制实施办法",
        "issuing_authority": "河北省人民政府",
        "region": "河北省",
        "promulgated_on": "2009年10月29日",
        "effective_on": "2009年12月1日",
        "articles": [
            {
                "article_no": "第一条",
                "chapter_title": None,
                "heading_path": [],
                "text": "为明确和落实消防安全责任，制定本办法。",
            }
        ],
    }

    chunks = build_chunks(structured)

    assert chunks[0]["path"] == "河北省消防安全责任制实施办法 > 第一条"
    assert chunks[0]["heading_path"] == []


def test_build_chunks_matches_real_structured_fixture():
    structured = json.loads(
        (FIXTURE_DIR / "xiaofangfa_article_62_structured.json").read_text(encoding="utf-8")
    )

    chunks = build_chunks(structured, max_chunk_chars=300)

    expected_lines = (
        FIXTURE_DIR / "xiaofangfa_article_62_expected.jsonl"
    ).read_text(encoding="utf-8").splitlines()

    assert [json.dumps(chunk, ensure_ascii=False) for chunk in chunks] == expected_lines


def test_write_chunks_persists_jsonl(tmp_path: Path):
    structured = {
        "document_id": "xiaofangfa_2019",
        "title": "中华人民共和国消防法",
        "issuing_authority": None,
        "region": "全国",
        "promulgated_on": None,
        "effective_on": "2009年5月1日",
        "articles": [
            {
                "article_no": "第二条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "国家实行消防安全责任制。",
            }
        ],
    }

    chunks = build_chunks(structured)
    output_path = write_chunks(chunks, "xiaofangfa_2019", tmp_path / "data" / "chunks")

    assert output_path == tmp_path / "data" / "chunks" / "xiaofangfa_2019.jsonl"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["chunk_id"] == "xiaofangfa_2019#article-1"
    assert payload["path"] == "中华人民共和国消防法 > 第一章 总则 > 第二条"
