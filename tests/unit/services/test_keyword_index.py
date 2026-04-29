import pytest

from app.services.keyword_index import (
    append_keyword_index,
    build_keyword_index,
    KeywordIndexConflictError,
    search_keyword_index,
)


def test_keyword_index_returns_matching_article(tmp_path):
    chunks = [
        {
            "chunk_id": "a1",
            "document_id": "doc-1",
            "title": "消防法",
            "path": "法 > 章 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
            "chapter_title": "第一章 总则",
            "region": "全国",
            "promulgated_on": None,
            "effective_on": "2009年5月1日",
        },
        {
            "chunk_id": "a2",
            "document_id": "doc-1",
            "title": "消防法",
            "path": "法 > 章 > 第二十八条",
            "text": "任何单位不得损坏消防设施。",
            "article_no": "第二十八条",
            "chapter_title": "第三章",
            "region": "全国",
            "promulgated_on": None,
            "effective_on": "2009年5月1日",
        },
    ]
    db_path = tmp_path / "retrieval.db"

    build_keyword_index(chunks, db_path)
    results = search_keyword_index("消防设施", db_path, top_k=3)

    assert results[0]["chunk_id"] == "a2"
    assert results[0]["path"] == "法 > 章 > 第二十八条"


def test_keyword_index_supports_region_filter(tmp_path):
    chunks = [
        {
            "chunk_id": "national-1",
            "document_id": "doc-1",
            "title": "消防法",
            "path": "法 > 章 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
            "chapter_title": "第一章 总则",
            "region": "全国",
            "promulgated_on": None,
            "effective_on": "2009年5月1日",
        },
        {
            "chunk_id": "hebei-1",
            "document_id": "doc-2",
            "title": "河北省消防条例",
            "path": "条例 > 第一章 总则 > 第二条",
            "text": "河北省实行消防安全责任制。",
            "article_no": "第二条",
            "chapter_title": "第一章 总则",
            "region": "河北省",
            "promulgated_on": None,
            "effective_on": "2010年7月1日",
        },
    ]
    db_path = tmp_path / "retrieval.db"

    build_keyword_index(chunks, db_path)
    results = search_keyword_index("消防安全责任制", db_path, top_k=5, region="河北省")

    assert [item["chunk_id"] for item in results] == ["hebei-1"]


def test_append_keyword_index_adds_new_document_without_rebuilding_existing_rows(tmp_path):
    db_path = tmp_path / "retrieval.db"
    build_keyword_index(
        [
            {
                "chunk_id": "old-1",
                "document_id": "old_doc",
                "title": "旧法规",
                "path": "旧法规 > 第一条",
                "text": "旧消防设施要求。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        db_path,
    )

    append_keyword_index(
        [
            {
                "chunk_id": "new-1",
                "document_id": "new_doc",
                "title": "新法规",
                "path": "新法规 > 第一条",
                "text": "新增消防安全责任。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        db_path,
        document_id="new_doc",
    )

    assert search_keyword_index("旧消防设施", db_path, top_k=5)[0]["chunk_id"] == "old-1"
    assert search_keyword_index("新增消防安全责任", db_path, top_k=5)[0]["chunk_id"] == "new-1"

    with pytest.raises(KeywordIndexConflictError, match="关键词索引已有该 document_id"):
        append_keyword_index([], db_path, document_id="new_doc")
