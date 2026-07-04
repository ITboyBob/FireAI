import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

from app.core.settings import Settings
from app.services.keyword_index import search_keyword_index
from app.services.vector_index import load_vector_map


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_WS3_ARTICLE_COUNT = 29
EXPECTED_WS3_CHUNK_COUNT = 34

WS3_DOCUMENT_ID = "doc_1e3762c74ebf"
WS3_SOURCE_RELATIVE = "督察、处罚与监管/河北省消防救援机构执法过错责任追究规定.doc"
WS3_SOURCE_PATH = PROJECT_ROOT / "法律文本" / "todo" / WS3_SOURCE_RELATIVE

W_S1_DOCUMENT_IDS = [
    "doc_e656eadc89d0",
    "doc_69c2e31cbdd7",
    "doc_2373a58c077e",
    "doc_d42834f991f1",
    "doc_7217aa1967d5",
    "doc_4cefe1e66632",
    "doc_0d9a0b22e189",
    "doc_405dcbcae152",
    "doc_17f21c6a42ec",
    "doc_8984bc91baeb",
]
W_S2_DOCUMENT_IDS = ["doc_d97773f1500c", "doc_0e84d13a099b", "doc_aa2b9b6c20ab"]

W_S1_WS2_KEYWORD_QUERIES: dict[str, str] = {
    "doc_e656eadc89d0": "火灾高危单位消防安全管理规定",
    "doc_69c2e31cbdd7": "高层民用建筑消防安全管理",
    "doc_2373a58c077e": "公共娱乐场所管理",
    "doc_d42834f991f1": "消防救援衔",
    "doc_7217aa1967d5": "安全生产行政执法与刑事司法衔接",
    "doc_4cefe1e66632": "河北省消防安全领域信用管理",
    "doc_0d9a0b22e189": "消防技术服务监督管理",
    "doc_405dcbcae152": "消防行政执法裁量实施办法",
    "doc_17f21c6a42ec": "火灾事故调查处理",
    "doc_8984bc91baeb": "消防产品监督管理",
    "doc_d97773f1500c": "消防监督检查规定",
    "doc_0e84d13a099b": "河北省消防设施管理规定",
    "doc_aa2b9b6c20ab": "社会消防安全教育培训规定",
}


@pytest.fixture(scope="module")
def real_settings() -> Settings:
    return Settings()


def _count_keyword_rows(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])


def _keyword_rows_for_document(db_path: Path, document_id: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(
            connection.execute(
                "SELECT count(*) FROM chunks WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )


def test_ws3_formal_artifacts_exist_and_match_manifest(real_settings: Settings) -> None:
    """W-S3 正式产物在 normalized、structured、chunks 中各出现一次，且与 manifest 一致。"""
    data_dir = real_settings.data_dir
    source_sha256 = sha256(WS3_SOURCE_PATH.read_bytes()).hexdigest()

    normalized_path = data_dir / "normalized" / f"{WS3_DOCUMENT_ID}.txt"
    structured_path = data_dir / "structured" / f"{WS3_DOCUMENT_ID}.json"
    chunks_path = data_dir / "chunks" / f"{WS3_DOCUMENT_ID}.jsonl"

    assert normalized_path.exists()
    assert structured_path.exists()
    assert chunks_path.exists()

    manifest = json.loads(
        (real_settings.manifests_dir / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )
    ws3_entries = [i for i in manifest["imports"] if i["document_id"] == WS3_DOCUMENT_ID]
    assert len(ws3_entries) == 1, "manifest 中只能有一条 W-S3 记录"

    entry = ws3_entries[0]
    assert entry["source_sha256"] == source_sha256
    assert entry["chunk_count"] == EXPECTED_WS3_CHUNK_COUNT
    assert entry["source_name"] == WS3_SOURCE_PATH.stem


def test_ws3_formal_counts_increment_by_expected_amounts(real_settings: Settings) -> None:
    """正式增量为 document +1，chunk/vector +34，manifest +1。"""
    data_dir = real_settings.data_dir
    index_dir = real_settings.index_dir
    manifest_path = real_settings.manifests_dir / "incremental_imports.json"

    # 这些常量来自 Task 6/7 对干净基线的记录，表示 W-S3 导入前的稳定状态。
    baseline_manifest_count = 13
    baseline_keyword_rows = 842
    baseline_vector_count = 842

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["imports"]) == baseline_manifest_count + 1

    keyword_rows = _count_keyword_rows(index_dir / "retrieval.db")
    vector_count = len(load_vector_map(index_dir / "vector_map.json"))

    assert keyword_rows == baseline_keyword_rows + EXPECTED_WS3_CHUNK_COUNT
    assert vector_count == baseline_vector_count + EXPECTED_WS3_CHUNK_COUNT
    assert _keyword_rows_for_document(index_dir / "retrieval.db", WS3_DOCUMENT_ID) == EXPECTED_WS3_CHUNK_COUNT


def test_ws3_formal_structured_has_clean_articles(real_settings: Settings) -> None:
    """结构化文件包含 29 条正文，且尾部污染物未进入正文。"""
    structured_path = real_settings.data_dir / "structured" / f"{WS3_DOCUMENT_ID}.json"
    structured = json.loads(structured_path.read_text(encoding="utf-8"))

    assert structured["content_class"] == "S3"
    assert structured["boundary_status"] == "confirmed"
    assert len(structured["articles"]) == EXPECTED_WS3_ARTICLE_COUNT

    structured_text = json.dumps(structured, ensure_ascii=False)
    assert "行政执法监督文书" not in structured_text
    assert "姓名：" not in structured_text
    assert "单位：" not in structured_text
    assert "PAGE" not in structured_text

    last_article = structured["articles"][-1]
    assert last_article["article_no"] == "第二十九条"
    assert "行政执法监督文书" not in last_article.get("text", "")


def test_ws3_formal_chunks_are_clean(real_settings: Settings) -> None:
    """切块文件包含 34 条干净 chunk，且均绑定同一 document_id。"""
    chunks_path = real_settings.data_dir / "chunks" / f"{WS3_DOCUMENT_ID}.jsonl"
    with chunks_path.open(encoding="utf-8") as handle:
        chunks = [json.loads(line) for line in handle]

    assert len(chunks) == EXPECTED_WS3_CHUNK_COUNT
    for chunk in chunks:
        assert chunk["document_id"] == WS3_DOCUMENT_ID
        assert chunk["content_class"] == "S3"
        assert "行政执法监督文书" not in chunk["text"]
        assert "姓名：" not in chunk["text"]
        assert "单位：" not in chunk["text"]
        assert "PAGE" not in chunk["text"]


def test_ws3_formal_batch_report_matches_commit(real_settings: Settings) -> None:
    """正式批次报告记录 committed=1、v3 PASS 和来源摘要。"""
    data_dir = real_settings.data_dir
    source_sha256 = sha256(WS3_SOURCE_PATH.read_bytes()).hexdigest()

    batch_dirs = list((data_dir / "manifests" / "legal_ingestion_batches").iterdir())
    # 只取包含 W-S3 质量报告且状态为 committed 的批次报告。
    ws3_report_path = None
    for batch_dir in batch_dirs:
        candidate = batch_dir / f"{batch_dir.name}.batch.json"
        if not candidate.exists():
            continue
        report = json.loads(candidate.read_text(encoding="utf-8"))
        for result in report.get("results", []):
            if result["document_id"] == WS3_DOCUMENT_ID and result["final_state"] == "committed":
                ws3_report_path = candidate
                break
        if ws3_report_path:
            break

    assert ws3_report_path is not None, "未找到 W-S3 正式 committed 批次报告"
    report = json.loads(ws3_report_path.read_text(encoding="utf-8"))
    assert len(report["results"]) == 1
    result = report["results"][0]
    assert result["source_sha256"] == source_sha256
    assert result["final_state"] == "committed"
    assert result["quality_report_path"]

    quality = json.loads(Path(result["quality_report_path"]).read_text(encoding="utf-8"))
    assert quality["ruleset_version"] == "legal-quality-v3"
    assert quality["overall"] == "pass"
    gate_ids = {gate["gate_id"]: gate for gate in quality["gates"]}
    for gate_id in [
        "s3_tail_exclusion_presence",
        "s3_tail_position",
        "s3_tail_coverage",
        "s3_output_purity",
    ]:
        assert gate_ids[gate_id]["outcome"] == "pass"


def test_ws3_formal_keyword_retrieval_hits_target_and_not_tail(
    real_settings: Settings,
) -> None:
    """标题和正文关键词检索命中目标文档，尾部模板文本不命中。"""
    db_path = real_settings.index_dir / "retrieval.db"

    title_hits = search_keyword_index(WS3_SOURCE_PATH.stem, db_path, top_k=5)
    assert any(hit["document_id"] == WS3_DOCUMENT_ID for hit in title_hits)

    body_hits = search_keyword_index("执法办案责任制", db_path, top_k=5)
    assert any(
        hit["document_id"] == WS3_DOCUMENT_ID and hit.get("article_no") == "第一条"
        for hit in body_hits
    )

    tail_hits = search_keyword_index("行政执法监督文书", db_path, top_k=5)
    assert not any(hit["document_id"] == WS3_DOCUMENT_ID for hit in tail_hits)


def test_ws1_ws2_documents_still_exist_and_retrievable(real_settings: Settings) -> None:
    """W-S1 8 份、W-S2 2 份已验收文件仍在 manifest、索引中且可关键词检索。"""
    manifest = json.loads(
        (real_settings.manifests_dir / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_ids = {i["document_id"] for i in manifest["imports"]}

    for document_id in W_S1_DOCUMENT_IDS + W_S2_DOCUMENT_IDS:
        assert document_id in manifest_ids
        assert (real_settings.data_dir / "normalized" / f"{document_id}.txt").exists()
        assert (real_settings.data_dir / "structured" / f"{document_id}.json").exists()
        assert (real_settings.data_dir / "chunks" / f"{document_id}.jsonl").exists()

    db_path = real_settings.index_dir / "retrieval.db"
    for document_id in W_S1_DOCUMENT_IDS + W_S2_DOCUMENT_IDS:
        query = W_S1_WS2_KEYWORD_QUERIES[document_id]
        hits = search_keyword_index(query, db_path, top_k=3)
        assert hits and hits[0]["document_id"] == document_id, (
            f"文档 {document_id} 按关键词 '{query}' 未命中自身"
        )
