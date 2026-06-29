from pathlib import Path

import json

from app.services.legal_ingestion_orchestrator import run_legal_ingestion
from app.services.query_normalizer import normalize_query
from app.services.retriever import Retriever, fuse_results
from tests.integration.pipeline.test_build_pipeline import (
    FakeEmbedder,
    MINI_FIRE_LAW,
    _write_docx,
)
from tests.integration.pipeline.test_incremental_import_pipeline import (
    _build_existing_corpus_and_index,
)

class FakeEmbedder:
    def encode_queries(self, texts):
        assert texts
        return [[1.0, 0.0]]

    def encode_documents(self, texts):
        assert texts
        return [[1.0, 0.0] for _ in texts]


class FakeVectorStore:
    def search(self, query_vector, *, top_k):
        assert query_vector == [1.0, 0.0]
        assert top_k == 9
        return [
            {"position": 0, "score": 0.8},
            {"position": 1, "score": 0.6},
        ]


def test_fuse_results_deduplicates_by_chunk_id():
    keyword_hits = [{"chunk_id": "a1", "score": 0.9}]
    vector_hits = [{"chunk_id": "a1", "score": 0.8}, {"chunk_id": "a2", "score": 0.7}]

    fused = fuse_results(keyword_hits, vector_hits, top_k=3)

    assert [item["chunk_id"] for item in fused] == ["a1", "a2"]
    assert fused[0]["sources"] == ["keyword", "vector"]
    assert fused[1]["sources"] == ["vector"]


def test_retriever_search_applies_metadata_hints_and_preserves_sources():
    def fake_keyword_search(query, db_path, *, top_k, region=None, promulgated_on=None, effective_on=None):
        assert db_path == Path("data/index/retrieval.db")
        assert top_k == 9
        assert region == "河北省"
        assert effective_on == "2010年7月1日"
        assert query in {
            "河北消防条例第28条自2010年7月1日起施行吗",
            "河北省消防条例",
            "第二十八条",
            "2010年7月1日",
            "2010年",
        }
        return [
            {
                "chunk_id": "hebei-28",
                "document_id": "hebei_xiaofang_tiaoli",
                "title": "河北省消防条例",
                "path": "河北省消防条例 > 第二十八条",
                "text": "有关消防职责的规定。",
                "article_no": "第二十八条",
                "region": "河北省",
                "promulgated_on": None,
                "effective_on": "2010年7月1日",
                "score": -3.0,
            },
            {
                "chunk_id": "national-28",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第二十八条",
                "text": "任何单位不得损坏消防设施。",
                "article_no": "第二十八条",
                "region": "全国",
                "promulgated_on": "2009年10月29日",
                "effective_on": "2009年5月1日",
                "score": -2.0,
            },
        ]

    retriever = Retriever(
        keyword_db_path=Path("data/index/retrieval.db"),
        vector_store=FakeVectorStore(),
        vector_map=[
            {
                "position": 0,
                "chunk_id": "hebei-28",
                "document_id": "hebei_xiaofang_tiaoli",
                "title": "河北省消防条例",
                "path": "河北省消防条例 > 第二十八条",
                "text": "有关消防职责的规定。",
                "article_no": "第二十八条",
                "region": "河北省",
                "promulgated_on": None,
                "effective_on": "2010年7月1日",
            },
            {
                "position": 1,
                "chunk_id": "national-28",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第二十八条",
                "text": "任何单位不得损坏消防设施。",
                "article_no": "第二十八条",
                "region": "全国",
                "promulgated_on": "2009年10月29日",
                "effective_on": "2009年5月1日",
            },
        ],
        embedder=FakeEmbedder(),
        keyword_search=fake_keyword_search,
    )

    results = retriever.search(
        normalize_query("河北消防条例第28条自2010年7月1日起施行吗"),
        top_k=3,
    )

    assert [item["chunk_id"] for item in results] == ["hebei-28"]
    assert results[0]["document_id"] == "hebei_xiaofang_tiaoli"
    assert results[0]["path"] == "河北省消防条例 > 第二十八条"
    assert results[0]["sources"] == ["keyword", "vector"]


def test_retriever_search_prefers_single_canonical_title_scope():
    def fake_keyword_search(query, db_path, *, top_k, region=None, promulgated_on=None, effective_on=None):
        assert query in {"消防法第二条责任制", "中华人民共和国消防法", "第二条"}
        return [
            {
                "chunk_id": "national-2",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
                "text": "国家实行消防安全责任制。",
                "article_no": "第二条",
                "region": "全国",
                "promulgated_on": None,
                "effective_on": "2009年5月1日",
                "score": -3.0,
            },
            {
                "chunk_id": "hebei-2",
                "document_id": "hebei_xiaofang_tiaoli",
                "title": "河北省消防条例",
                "path": "河北省消防条例 > 第一章 总则 > 第二条",
                "text": "河北省实行消防安全责任制。",
                "article_no": "第二条",
                "region": "河北省",
                "promulgated_on": None,
                "effective_on": "2010年7月1日",
                "score": -2.0,
            },
        ]

    retriever = Retriever(
        keyword_db_path=Path("data/index/retrieval.db"),
        keyword_search=fake_keyword_search,
    )

    results = retriever.search(normalize_query("消防法第二条责任制"), top_k=3)

    assert [item["chunk_id"] for item in results] == ["national-2"]


def test_retriever_finds_committed_ws1_article(tmp_path: Path) -> None:
    """Retriever 能从真实 W-S1 提交后的索引中召回对应 chunk。"""
    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _write_docx(
        MINI_FIRE_LAW,
        raw_dir / "消防法--2019年4月23日.docx",
    )
    _build_existing_corpus_and_index(raw_dir=raw_dir, data_dir=data_dir)

    project_root = Path(__file__).resolve().parents[3]
    baseline_path = project_root / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    ws1_cases = [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S1"
    ]
    case = ws1_cases[0]
    source_path = project_root / "法律文本" / "todo" / case["relative_path"]
    assert source_path.exists(), f"本机缺少真实 W-S1 源文件: {case['relative_path']}"

    summary = run_legal_ingestion(
        sources=[source_path],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="ws1-retriever",
        dry_run=False,
    )
    document_id = summary.committed_document_ids[0]

    retriever = Retriever.from_disk(
        keyword_db_path=data_dir / "index" / "retrieval.db",
        vector_index_path=data_dir / "index" / "faiss.index",
        vector_map_path=data_dir / "index" / "vector_map.json",
        embedder=FakeEmbedder(),
    )
    results = retriever.search(source_path.stem, top_k=3)
    assert any(result["document_id"] == document_id for result in results)
