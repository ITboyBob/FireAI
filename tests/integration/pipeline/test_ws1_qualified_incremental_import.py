import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.incremental_import import IncrementalImportError
from app.services.keyword_index import search_keyword_index
from app.services.legal_ingestion_batch import load_batch_report
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


def _load_ws1_cases() -> list[dict]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S1"
    ]


def _run_id_for(case: dict) -> str:
    return f"ws1-qual-{sha256(case['relative_path'].encode('utf-8')).hexdigest()[:12]}"


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


def test_ws1_qualified_incremental_import_commits_all_eight_files(
    seeded_data_dir: Path,
) -> None:
    """8 份 W-S1 真实文件逐文件提交后，正式产物、关键词索引、向量映射和 manifest 一致。"""
    data_dir = seeded_data_dir
    committed_document_ids: list[str] = []

    for case in _load_ws1_cases():
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

        assert (data_dir / "normalized" / f"{document_id}.txt").exists()
        assert (data_dir / "structured" / f"{document_id}.json").exists()
        assert (data_dir / "chunks" / f"{document_id}.jsonl").exists()

        hits = search_keyword_index(
            source_path.stem, data_dir / "index" / "retrieval.db", top_k=5
        )
        assert any(hit["document_id"] == document_id for hit in hits), (
            f"{case['relative_path']} 标题关键词检索未命中"
        )

        vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
        assert [item["position"] for item in vector_map] == list(range(len(vector_map)))
        assert any(item["document_id"] == document_id for item in vector_map)

    manifest = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(encoding="utf-8")
    )
    assert [item["document_id"] for item in manifest["imports"]] == committed_document_ids


def test_ws1_qualified_incremental_import_rejects_duplicate(
    seeded_data_dir: Path,
) -> None:
    """重复导入同一来源必须因 document_id 冲突失败，且不得改变已有索引。"""
    case = _load_ws1_cases()[0]
    source_path = TODO_ROOT / case["relative_path"]
    run_id = _run_id_for(case)

    run_legal_ingestion(
        sources=[source_path],
        data_dir=seeded_data_dir,
        index_dir=seeded_data_dir / "index",
        manifest_path=seeded_data_dir / "manifests" / "incremental_imports.json",
        staging_root=seeded_data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id=run_id,
        dry_run=False,
    )

    vector_map_before = (
        seeded_data_dir / "index" / "vector_map.json"
    ).read_text(encoding="utf-8")
    manifest_before = (
        seeded_data_dir / "manifests" / "incremental_imports.json"
    ).read_text(encoding="utf-8")
    keyword_count_before = _count_keyword_rows(
        seeded_data_dir / "index" / "retrieval.db"
    )

    with pytest.raises(IncrementalImportError, match="document_id"):
        run_legal_ingestion(
            sources=[source_path],
            data_dir=seeded_data_dir,
            index_dir=seeded_data_dir / "index",
            manifest_path=seeded_data_dir / "manifests" / "incremental_imports.json",
            staging_root=seeded_data_dir / ".staging",
            embedder=FakeEmbedder(),
            run_id=f"{run_id}-retry",
            dry_run=False,
        )

    assert (
        seeded_data_dir / "index" / "vector_map.json"
    ).read_text(encoding="utf-8") == vector_map_before
    assert (
        seeded_data_dir / "manifests" / "incremental_imports.json"
    ).read_text(encoding="utf-8") == manifest_before
    assert (
        _count_keyword_rows(seeded_data_dir / "index" / "retrieval.db")
        == keyword_count_before
    )


def test_ws1_batch_import_isolates_failure(seeded_data_dir: Path, tmp_path: Path) -> None:
    """批次中不合格文件进入 review_required，成功文件仍正常提交并可检索。"""
    good_case = _load_ws1_cases()[0]
    good_source = TODO_ROOT / good_case["relative_path"]
    bad_source = tmp_path / "bad.txt"
    bad_source.write_text("这不是一份可识别的法规文件。", encoding="utf-8")

    summary = run_legal_ingestion(
        sources=[good_source, bad_source],
        data_dir=seeded_data_dir,
        index_dir=seeded_data_dir / "index",
        manifest_path=seeded_data_dir / "manifests" / "incremental_imports.json",
        staging_root=seeded_data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="ws1-isolation",
        dry_run=False,
    )

    assert len(summary.committed_document_ids) == 1
    good_document_id = summary.committed_document_ids[0]

    assert not (seeded_data_dir / "normalized" / "bad.txt").exists()

    batch_report = load_batch_report(summary.batch_report_path)
    states = {
        result.relative_path: result.final_state.value
        for result in batch_report.results
    }
    assert states[good_source.name] == "committed"
    assert states[bad_source.name] == "review_required"

    hits = search_keyword_index(
        good_source.stem, seeded_data_dir / "index" / "retrieval.db", top_k=5
    )
    assert any(hit["document_id"] == good_document_id for hit in hits)
