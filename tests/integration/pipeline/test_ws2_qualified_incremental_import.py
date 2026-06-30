import json
from hashlib import sha1, sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.keyword_index import search_keyword_index
from app.services.legal_ingestion_batch import FileState, load_batch_report
from app.services.legal_ingestion_orchestrator import run_legal_ingestion
from app.services.vector_index import load_vector_map
from tests.integration.pipeline.test_build_pipeline import (
    FakeEmbedder,
    MINI_FIRE_LAW,
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


def _load_ws2_cases() -> list[dict]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S2"
    ]


def _run_id_for(case: dict) -> str:
    return f"ws2-qual-{sha256(case['relative_path'].encode('utf-8')).hexdigest()[:12]}"


def _document_id_for(source_path: Path) -> str:
    return f"doc_{sha1(source_path.stem.encode('utf-8')).hexdigest()[:12]}"


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


def test_ws2_qualified_incremental_import_commits_two_files(
    seeded_data_dir: Path,
) -> None:
    """两份 W-S2 真实文件逐文件提交后，正式产物、索引和 manifest 各增加对应记录。"""
    data_dir = seeded_data_dir
    cases = _load_ws2_cases()
    assert len(cases) == 2

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_before = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_before = (
        json.loads(
            (data_dir / "manifests" / "incremental_imports.json").read_text(
                encoding="utf-8"
            )
        )
        if (data_dir / "manifests" / "incremental_imports.json").exists()
        else {"imports": []}
    )

    committed_document_ids: list[str] = []
    total_new_chunks = 0
    for case in cases:
        source_path = TODO_ROOT / case["relative_path"]
        assert source_path.exists(), f"缺失真实源文件: {case['relative_path']}"

        summary = run_legal_ingestion(
            sources=[source_path],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=FakeEmbedder(),
            run_id=_run_id_for(case),
            dry_run=False,
        )

        assert len(summary.committed_document_ids) == 1
        document_id = summary.committed_document_ids[0]
        committed_document_ids.append(document_id)
        total_new_chunks += summary.total_chunks

        assert (data_dir / "normalized" / f"{document_id}.txt").exists()
        assert (data_dir / "structured" / f"{document_id}.json").exists()
        assert (data_dir / "chunks" / f"{document_id}.jsonl").exists()

        structured = json.loads(
            (data_dir / "structured" / f"{document_id}.json").read_text(
                encoding="utf-8"
            )
        )
        assert len(structured["articles"]) == case["expected_article_count"]

        hits = search_keyword_index(
            source_path.stem, data_dir / "index" / "retrieval.db", top_k=5
        )
        assert any(hit["document_id"] == document_id for hit in hits), (
            f"{case['relative_path']} 标题关键词检索未命中"
        )

        vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
        assert [item["position"] for item in vector_map] == list(range(len(vector_map)))
        assert any(item["document_id"] == document_id for item in vector_map)

    keyword_rows_after = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_after = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_after = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )

    assert keyword_rows_after - keyword_rows_before == total_new_chunks
    assert len(vector_map_after) - len(vector_map_before) == total_new_chunks
    assert len(manifest_after["imports"]) - len(manifest_before["imports"]) == 2
    assert (
        [item["document_id"] for item in manifest_after["imports"]][-2:]
        == committed_document_ids
    )

    for case, document_id in zip(cases, committed_document_ids):
        manifest_record = next(
            item
            for item in manifest_after["imports"]
            if item["document_id"] == document_id
        )
        source_path = TODO_ROOT / case["relative_path"]
        assert (
            manifest_record["source_sha256"]
            == sha256(source_path.read_bytes()).hexdigest()
        )
        assert manifest_record["chunk_count"] > 0


def test_ws2_qualified_incremental_import_isolates_staged_digest_failure(
    seeded_data_dir: Path,
) -> None:
    """第二份文件 staged digest 校验失败时，第一份已提交文件不受影响。"""
    data_dir = seeded_data_dir
    cases = _load_ws2_cases()
    assert len(cases) == 2

    good_source = TODO_ROOT / cases[0]["relative_path"]
    bad_source = TODO_ROOT / cases[1]["relative_path"]
    bad_document_id = _document_id_for(bad_source)

    def _bad_sha256_for_second(path: Path) -> str:
        resolved = path.resolve()
        if resolved == bad_source.resolve() or path.name.startswith(bad_document_id):
            return "0" * 64
        return sha256(path.read_bytes()).hexdigest()

    with patch(
        "app.services.legal_qualified_import._sha256_file",
        side_effect=_bad_sha256_for_second,
    ):
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=FakeEmbedder(),
            run_id="ws2-digest-isolation",
            dry_run=False,
        )

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {result.relative_path: result.final_state for result in batch_report.results}
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert (data_dir / "normalized" / f"{good_document_id}.txt").exists()
    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()

    manifest = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )
    assert good_document_id in {item["document_id"] for item in manifest["imports"]}
    assert bad_document_id not in {item["document_id"] for item in manifest["imports"]}

    hits = search_keyword_index(
        good_source.stem, data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)


def test_ws2_qualified_incremental_import_rolls_back_index_publish_failure(
    seeded_data_dir: Path,
) -> None:
    """第二份文件 manifest 写入前失败时，其语料和索引应回滚，第一份文件保持提交。"""
    data_dir = seeded_data_dir
    cases = _load_ws2_cases()
    assert len(cases) == 2

    good_source = TODO_ROOT / cases[0]["relative_path"]
    bad_source = TODO_ROOT / cases[1]["relative_path"]
    bad_document_id = _document_id_for(bad_source)

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")

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
            manifest_path,
            document_id=document_id,
            **kwargs,
        )

    incremental_module.append_import_record = _failing_append_import_record
    try:
        summary = run_legal_ingestion(
            sources=[good_source, bad_source],
            data_dir=data_dir,
            index_dir=data_dir / "index",
            manifest_path=data_dir / "manifests" / "incremental_imports.json",
            staging_root=data_dir / ".staging",
            embedder=FakeEmbedder(),
            run_id="ws2-index-rollback",
            dry_run=False,
        )
    finally:
        incremental_module.append_import_record = original_append_import_record

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    batch_report = load_batch_report(summary.batch_report_path)
    states = {result.relative_path: result.final_state for result in batch_report.results}
    assert states[good_source.name] == FileState.COMMITTED
    assert states[bad_source.name] == FileState.FAILED

    assert (data_dir / "normalized" / f"{good_document_id}.txt").exists()
    assert not (data_dir / "normalized" / f"{bad_document_id}.txt").exists()
    assert not (data_dir / "structured" / f"{bad_document_id}.json").exists()
    assert not (data_dir / "chunks" / f"{bad_document_id}.jsonl").exists()

    manifest = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["document_id"] for item in manifest["imports"]] == [good_document_id]

    vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
    assert bad_document_id not in {item["document_id"] for item in vector_map}
    assert good_document_id in {item["document_id"] for item in vector_map}

    keyword_rows_after = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    assert keyword_rows_after == keyword_rows_before + _keyword_rows_for_documents(
        data_dir / "index" / "retrieval.db", [good_document_id]
    )


def _keyword_rows_for_documents(db_path: Path, document_ids: list[str]) -> int:
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        placeholders = ",".join("?" * len(document_ids))
        return int(
            connection.execute(
                f"SELECT count(*) FROM chunks WHERE document_id IN ({placeholders})",
                document_ids,
            ).fetchone()[0]
        )
