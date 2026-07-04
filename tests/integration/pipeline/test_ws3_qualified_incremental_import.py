import json
from hashlib import sha1, sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.keyword_index import search_keyword_index
from app.services.legal_ingestion_batch import FileState, load_batch_report
from app.services.legal_ingestion_orchestrator import run_legal_ingestion
from app.services.retriever import Retriever
from app.services.vector_index import load_vector_map
from tests.integration.pipeline.test_build_pipeline import (
    FakeEmbedder,
    MINI_FIRE_LAW,
    MINI_HEBEI_REGULATION,
    _write_docx,
)
from tests.integration.pipeline.test_incremental_import_pipeline import (
    _build_existing_corpus_and_index,
    _count_keyword_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)

EXPECTED_WS3_ARTICLE_COUNT = 29
EXPECTED_WS3_CHUNK_COUNT = 34


class WS3FakeEmbedder(FakeEmbedder):
    """既能被向量索引构建使用，也能被 Retriever 查询使用。"""

    def encode(self, texts):
        return self.encode_documents(texts)


def _load_ws3_case() -> dict:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    cases = [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S3"
    ]
    assert len(cases) == 1
    return cases[0]


def _document_id_for(source_path: Path) -> str:
    return f"doc_{sha1(source_path.stem.encode('utf-8')).hexdigest()[:12]}"


def _make_good_source(tmp_path: Path) -> Path:
    """生成一个可独立提交通过的 W-S1 companion 文件，用于把单文件模式强转为批次模式。"""
    source_path = tmp_path / "河北省消防条例.docx"
    _write_docx(MINI_HEBEI_REGULATION, source_path)
    return source_path


def _manifest_document_ids(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {item["document_id"] for item in manifest.get("imports", [])}


def _keyword_rows_for_document(db_path: Path, document_id: str) -> int:
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        return int(
            connection.execute(
                "SELECT count(*) FROM chunks WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )


@pytest.fixture
def seeded_data_dir(tmp_path: Path) -> Path:
    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _write_docx(
        MINI_FIRE_LAW,
        raw_dir / "消防法--2019年4月23日.docx",
    )
    _build_existing_corpus_and_index(raw_dir=raw_dir, data_dir=data_dir)
    return data_dir


def test_ws3_qualified_incremental_import_commits_one_file(
    seeded_data_dir: Path,
) -> None:
    """唯一 W-S3 文件在临时目录提交后，语料、两类索引和 manifest 各增加对应记录。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    source_path = TODO_ROOT / case["relative_path"]
    before_digest = sha256(source_path.read_bytes()).hexdigest()

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_before_count = len(
        _manifest_document_ids(data_dir / "manifests" / "incremental_imports.json")
    )

    summary = run_legal_ingestion(
        sources=[source_path],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=WS3FakeEmbedder(),
        run_id="ws3-qualified-import",
        dry_run=False,
    )

    assert len(summary.committed_document_ids) == 1
    document_id = summary.committed_document_ids[0]
    assert summary.total_chunks == EXPECTED_WS3_CHUNK_COUNT

    assert (data_dir / "normalized" / f"{document_id}.txt").exists()
    assert (data_dir / "structured" / f"{document_id}.json").exists()
    assert (data_dir / "chunks" / f"{document_id}.jsonl").exists()

    structured = json.loads(
        (data_dir / "structured" / f"{document_id}.json").read_text(encoding="utf-8")
    )
    assert structured["content_class"] == "S3"
    assert structured["boundary_status"] == "confirmed"
    assert len(structured["articles"]) == EXPECTED_WS3_ARTICLE_COUNT

    keyword_rows_after = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_after = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_after = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )

    assert keyword_rows_after - keyword_rows_before == EXPECTED_WS3_CHUNK_COUNT
    assert len(vector_map_after) - len(vector_map_before) == EXPECTED_WS3_CHUNK_COUNT
    assert (
        len(manifest_after["imports"]) - manifest_before_count == 1
    )
    assert manifest_after["imports"][-1]["document_id"] == document_id
    assert manifest_after["imports"][-1]["chunk_count"] == EXPECTED_WS3_CHUNK_COUNT
    assert manifest_after["imports"][-1]["source_sha256"] == before_digest

    # 标题和正文独有条文可检索
    retriever = Retriever.from_disk(
        keyword_db_path=data_dir / "index" / "retrieval.db",
        vector_index_path=data_dir / "index" / "faiss.index",
        vector_map_path=data_dir / "index" / "vector_map.json",
        embedder=WS3FakeEmbedder(),
    )
    title_results = retriever.search(source_path.stem, top_k=3)
    assert any(result["document_id"] == document_id for result in title_results)

    body_results = retriever.search("执法办案责任制", top_k=5)
    assert any(
        result["document_id"] == document_id
        and result["article_no"] == "第一条"
        for result in body_results
    )

    # 只存在于尾部的模板文本不应命中正文
    tail_hits = search_keyword_index(
        "行政执法监督文书", data_dir / "index" / "retrieval.db", top_k=5
    )
    assert not any(hit["document_id"] == document_id for hit in tail_hits)


def test_ws3_qualified_incremental_import_rolls_back_source_digest_failure(
    seeded_data_dir: Path,
    tmp_path: Path,
) -> None:
    """W-S3 来源摘要不一致时导入失败，companion 文件和已有语料均不受影响。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    bad_source = TODO_ROOT / case["relative_path"]
    good_source = _make_good_source(tmp_path)
    bad_document_id = _document_id_for(bad_source)

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_ids_before = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )

    def _bad_sha256_for_source(path: Path) -> str:
        if path.resolve() == bad_source.resolve():
            return "0" * 64
        return sha256(path.read_bytes()).hexdigest()

    with patch(
        "app.services.legal_qualified_import._sha256_file",
        side_effect=_bad_sha256_for_source,
    ):
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=WS3FakeEmbedder(),
            run_id="ws3-source-digest-failure",
            dry_run=False,
        )

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {
        result.relative_path: result.final_state for result in batch_report.results
    }
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()
    assert not (data_dir / "structured" / f"{bad_document_id}.json").exists()
    assert not (data_dir / "chunks" / f"{bad_document_id}.jsonl").exists()

    vector_map_after = load_vector_map(data_dir / "index" / "vector_map.json")
    assert bad_document_id not in {
        item["document_id"] for item in vector_map_after
    }
    assert good_document_id in {item["document_id"] for item in vector_map_after}
    assert _count_keyword_rows(data_dir / "index" / "retrieval.db") == (
        keyword_rows_before + _keyword_rows_for_document(
            data_dir / "index" / "retrieval.db", good_document_id
        )
    )
    manifest_ids_after = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )
    assert bad_document_id not in manifest_ids_after
    assert manifest_ids_after == manifest_ids_before | {good_document_id}

    # companion 文件检索命中，说明其提交未被回滚
    hits = search_keyword_index(
        good_source.stem, data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)


def test_ws3_single_source_with_force_batch_returns_batch_report(
    seeded_data_dir: Path,
) -> None:
    """单来源在 force_batch=True 时仍走批次路径并返回 batch_report_path。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    source_path = TODO_ROOT / case["relative_path"]

    summary = run_legal_ingestion(
        sources=[source_path],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=WS3FakeEmbedder(),
        run_id="ws3-force-batch",
        dry_run=False,
        force_batch=True,
    )

    assert len(summary.committed_document_ids) == 1
    assert summary.batch_report_path is not None
    assert summary.batch_report_path.exists()

    report = json.loads(summary.batch_report_path.read_text(encoding="utf-8"))
    assert len(report["results"]) == 1
    assert report["results"][0]["document_id"] == summary.committed_document_ids[0]
    assert report["results"][0]["final_state"] == "committed"


def test_ws3_qualified_incremental_import_rolls_back_staged_digest_failure(
    seeded_data_dir: Path,
    tmp_path: Path,
) -> None:
    """W-S3 staged artifact 摘要校验失败时，companion 文件不受影响。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    bad_source = TODO_ROOT / case["relative_path"]
    good_source = _make_good_source(tmp_path)
    bad_document_id = _document_id_for(bad_source)

    def _bad_sha256_for_staged(path: Path) -> str:
        if path.name.startswith(bad_document_id):
            return "0" * 64
        return sha256(path.read_bytes()).hexdigest()

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_ids_before = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )

    with patch(
        "app.services.legal_qualified_import._sha256_file",
        side_effect=_bad_sha256_for_staged,
    ):
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=WS3FakeEmbedder(),
            run_id="ws3-staged-digest-failure",
            dry_run=False,
        )

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {
        result.relative_path: result.final_state for result in batch_report.results
    }
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()
    assert not (data_dir / "structured" / f"{bad_document_id}.json").exists()
    assert not (data_dir / "chunks" / f"{bad_document_id}.jsonl").exists()

    assert _count_keyword_rows(data_dir / "index" / "retrieval.db") == (
        keyword_rows_before + _keyword_rows_for_document(
            data_dir / "index" / "retrieval.db", good_document_id
        )
    )

    manifest_ids_after = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )
    assert bad_document_id not in manifest_ids_after
    assert manifest_ids_after == manifest_ids_before | {good_document_id}

    hits = search_keyword_index(
        good_source.stem, data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)


def test_ws3_qualified_incremental_import_rolls_back_index_publish_failure(
    seeded_data_dir: Path,
    tmp_path: Path,
) -> None:
    """W-S3 向量索引发布失败时，companion 文件提交成功，W-S3 语料回滚。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    bad_source = TODO_ROOT / case["relative_path"]
    good_source = _make_good_source(tmp_path)
    bad_document_id = _document_id_for(bad_source)

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_ids_before = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )

    import app.services.incremental_import as incremental_module

    original_append_vector_index = incremental_module.append_vector_index

    def _failing_append_vector_index(chunks, output_dir, *, embedder, document_id):
        if document_id == bad_document_id:
            raise RuntimeError("模拟向量索引发布失败")
        return original_append_vector_index(
            chunks, output_dir, embedder=embedder, document_id=document_id
        )

    incremental_module.append_vector_index = _failing_append_vector_index
    try:
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=WS3FakeEmbedder(),
            run_id="ws3-index-publish-failure",
            dry_run=False,
        )
    finally:
        incremental_module.append_vector_index = original_append_vector_index

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {
        result.relative_path: result.final_state for result in batch_report.results
    }
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()
    assert not (data_dir / "structured" / f"{bad_document_id}.json").exists()
    assert not (data_dir / "chunks" / f"{bad_document_id}.jsonl").exists()

    assert _count_keyword_rows(data_dir / "index" / "retrieval.db") == (
        keyword_rows_before + _keyword_rows_for_document(
            data_dir / "index" / "retrieval.db", good_document_id
        )
    )

    manifest_ids_after = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )
    assert bad_document_id not in manifest_ids_after
    assert manifest_ids_after == manifest_ids_before | {good_document_id}

    hits = search_keyword_index(
        good_source.stem, data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)


def test_ws3_qualified_incremental_import_rolls_back_manifest_publish_failure(
    seeded_data_dir: Path,
    tmp_path: Path,
) -> None:
    """W-S3 manifest 写入失败时，companion 文件提交成功，W-S3 语料和索引回滚。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    bad_source = TODO_ROOT / case["relative_path"]
    good_source = _make_good_source(tmp_path)
    bad_document_id = _document_id_for(bad_source)

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_ids_before = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )

    import app.services.incremental_import as incremental_module

    original_append_import_record = incremental_module.append_import_record

    def _failing_append_import_record(
        manifest_path: Path,
        *,
        document_id: str,
        **kwargs,
    ) -> None:
        if document_id == bad_document_id:
            raise RuntimeError("模拟 manifest 写入失败")
        return original_append_import_record(
            manifest_path, document_id=document_id, **kwargs
        )

    incremental_module.append_import_record = _failing_append_import_record
    try:
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=WS3FakeEmbedder(),
            run_id="ws3-manifest-publish-failure",
            dry_run=False,
        )
    finally:
        incremental_module.append_import_record = original_append_import_record

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {
        result.relative_path: result.final_state for result in batch_report.results
    }
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()
    assert not (data_dir / "structured" / f"{bad_document_id}.json").exists()
    assert not (data_dir / "chunks" / f"{bad_document_id}.jsonl").exists()
    assert (
        bad_document_id
        not in {
            item["document_id"]
            for item in load_vector_map(data_dir / "index" / "vector_map.json")
        }
    )
    assert _count_keyword_rows(data_dir / "index" / "retrieval.db") == (
        keyword_rows_before + _keyword_rows_for_document(
            data_dir / "index" / "retrieval.db", good_document_id
        )
    )

    manifest_ids_after = _manifest_document_ids(
        data_dir / "manifests" / "incremental_imports.json"
    )
    assert bad_document_id not in manifest_ids_after
    assert manifest_ids_after == manifest_ids_before | {good_document_id}

    hits = search_keyword_index(
        good_source.stem, data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)
