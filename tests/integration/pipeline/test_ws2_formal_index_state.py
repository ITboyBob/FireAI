import json
import sqlite3
from pathlib import Path

import pytest

from app.services.incremental_manifest import load_manifest
from app.services.keyword_index import search_keyword_index
from app.services.vector_index import load_vector_map


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
INDEX_DIR = DATA_DIR / "index"
MANIFEST_PATH = DATA_DIR / "manifests" / "incremental_imports.json"

WS2_CASES = [
    {
        "relative_path": "事故调查、问责与系统治理/河北省消防设施管理规定.docx",
        "document_id": "doc_0e84d13a099b",
        "source_sha256": (
            "176a9b8a07a127c614a0f8c16e2bd3508bd1df480e9672e6c44830ebf7db3c3c"
        ),
        "expected_article_count": 32,
        "expected_chunk_count": 33,
    },
    {
        "relative_path": "事故调查、问责与系统治理/社会消防安全教育培训规定.doc",
        "document_id": "doc_aa2b9b6c20ab",
        "source_sha256": (
            "71d4e0e053ea65738ddad16bb0b702e58913bdf074f266f4f6d1777506e5e20c"
        ),
        "expected_article_count": 37,
        "expected_chunk_count": 38,
    },
]


def _count_keyword_rows(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])


@pytest.mark.integration
def test_ws2_formal_index_state_reflects_imported_documents() -> None:
    """Task 10 正式导入后，真实 data/ 目录下两份 W-S2 文件的状态必须一致。"""
    assert MANIFEST_PATH.exists(), "缺少 manifest 文件"
    manifest = load_manifest(MANIFEST_PATH)
    manifest_document_ids = {item.document_id for item in manifest.imports}

    vector_map = load_vector_map(INDEX_DIR / "vector_map.json")
    vector_document_ids = {item["document_id"] for item in vector_map}
    keyword_rows = _count_keyword_rows(INDEX_DIR / "retrieval.db")

    total_expected_chunks = sum(case["expected_chunk_count"] for case in WS2_CASES)

    for case in WS2_CASES:
        document_id = case["document_id"]
        source_path = PROJECT_ROOT / "法律文本" / "todo" / case["relative_path"]

        assert document_id in manifest_document_ids, (
            f"{case['relative_path']} 未写入 manifest"
        )
        record = next(item for item in manifest.imports if item.document_id == document_id)
        assert record.source_sha256 == case["source_sha256"]
        assert record.chunk_count == case["expected_chunk_count"]

        assert (DATA_DIR / "normalized" / f"{document_id}.txt").exists()
        assert (DATA_DIR / "structured" / f"{document_id}.json").exists()
        assert (DATA_DIR / "chunks" / f"{document_id}.jsonl").exists()

        structured = json.loads(
            (DATA_DIR / "structured" / f"{document_id}.json").read_text(
                encoding="utf-8"
            )
        )
        assert structured["document_id"] == document_id
        assert len(structured["articles"]) == case["expected_article_count"]

        assert document_id in vector_document_ids, (
            f"{case['relative_path']} 未写入向量映射"
        )
        document_vectors = [
            item for item in vector_map if item["document_id"] == document_id
        ]
        assert len(document_vectors) == case["expected_chunk_count"]

        hits = search_keyword_index(
            source_path.stem, INDEX_DIR / "retrieval.db", top_k=5
        )
        assert any(hit["document_id"] == document_id for hit in hits), (
            f"{case['relative_path']} 标题关键词检索未命中"
        )

    assert keyword_rows >= total_expected_chunks
