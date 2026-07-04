import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.legal_ingestion_batch import load_batch_report
from app.services.legal_ingestion_orchestrator import run_legal_ingestion
from tests.integration.pipeline.test_build_pipeline import (
    FakeEmbedder,
    MINI_FIRE_LAW,
    _write_docx,
)
from tests.integration.pipeline.test_incremental_import_pipeline import (
    _build_existing_corpus_and_index,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)


EXPECTED_WS3_ARTICLE_COUNT = 29
EXPECTED_WS3_CHUNK_COUNT = 34


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


def _source_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def test_ws3_dry_run_batch_report_has_v3_pass_and_no_formal_writes(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    """CLI dry-run 对唯一 W-S3 文件生成 v3 PASS 报告，但不写正式语料。"""
    import runpy

    case = _load_ws3_case()
    source_path = TODO_ROOT / case["relative_path"]
    before_digest = _source_digest(source_path)

    data_dir = tmp_path / "data"
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INDEX_DIR", str(data_dir / "index"))

    result = module["main"](
        [
            "--batch-manifest",
            str(BASELINE_PATH),
            "--source-root",
            str(TODO_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S3",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=1" in captured.out
    assert "auto_passed=1" in captured.out
    assert "committed=0" in captured.out
    assert "review_required=0" in captured.out
    assert "failed=0" in captured.out
    assert "unsupported=0" in captured.out

    assert _source_digest(source_path) == before_digest
    assert not (data_dir / "normalized").exists() or not any(
        (data_dir / "normalized").iterdir()
    )
    assert not (data_dir / "structured").exists() or not any(
        (data_dir / "structured").iterdir()
    )
    assert not (data_dir / "chunks").exists() or not any(
        (data_dir / "chunks").iterdir()
    )
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()

    batch_report_path = next(
        (data_dir / "manifests" / "legal_ingestion_batches").iterdir()
    )
    batch_report = load_batch_report(batch_report_path / f"{batch_report_path.name}.batch.json")
    assert len(batch_report.results) == 1
    file_result = batch_report.results[0]
    assert file_result.final_state.value == "auto_passed"
    assert file_result.source_sha256 == before_digest

    quality_report = json.loads(
        Path(file_result.quality_report_path).read_text(encoding="utf-8")
    )
    assert quality_report["source_sha256"] == before_digest
    assert quality_report["ruleset_version"] == "legal-quality-v3"
    assert quality_report["overall"] == "pass"

    gates = {gate["gate_id"]: gate for gate in quality_report["gates"]}
    required_gates = [
        "source_identity",
        "document_identity",
        "boundary_confirmed",
        "article_start",
        "article_numbers",
        "article_non_empty",
        "body_purity",
        "exclusion_isolation",
        "cross_layer_consistency",
        "chunk_coverage",
        "s3_tail_exclusion_presence",
        "s3_tail_position",
        "s3_tail_coverage",
        "s3_output_purity",
    ]
    for gate_id in required_gates:
        assert gate_id in gates, f"缺少门禁 {gate_id}"
        assert gates[gate_id]["outcome"] == "pass", (
            f"门禁 {gate_id} 未通过: {gates[gate_id].get('reason_code')}"
        )

    assert gates["article_numbers"]["measured"]["article_count"] == EXPECTED_WS3_ARTICLE_COUNT
    assert gates["s3_tail_exclusion_presence"]["measured"]["tail_range_count"] >= 1

    measured = gates["s3_tail_exclusion_presence"]["measured"]
    excluded_kinds = {er["kind"] for er in measured.get("tail_ranges", [])}
    assert "attachment_index" in excluded_kinds
    assert "form_template" in excluded_kinds
    assert "trailing_print_metadata" in excluded_kinds

    report_text = json.dumps(quality_report, ensure_ascii=False)
    assert "行政执法监督文书" not in report_text
    assert "姓名：" not in report_text
    assert "单位：" not in report_text
    assert "PAGE" not in report_text


def test_ws3_real_import_in_temp_dir_freezes_clean_chunk_count(
    seeded_data_dir: Path,
):
    """在临时目录真实提交 W-S3，冻结干净 chunk 数为 34。"""
    data_dir = seeded_data_dir
    case = _load_ws3_case()
    source_path = TODO_ROOT / case["relative_path"]
    before_digest = _source_digest(source_path)

    keyword_rows_before = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    from app.services.vector_index import load_vector_map

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

    run_id = "ws3-clean-chunks-freeze"
    summary = run_legal_ingestion(
        sources=[source_path],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id=run_id,
        dry_run=False,
    )

    assert len(summary.committed_document_ids) == 1
    document_id = summary.committed_document_ids[0]
    assert summary.total_chunks == EXPECTED_WS3_CHUNK_COUNT

    assert (data_dir / "normalized" / f"{document_id}.txt").exists()
    assert (data_dir / "structured" / f"{document_id}.json").exists()
    assert (data_dir / "chunks" / f"{document_id}.jsonl").exists()

    normalized_text = (data_dir / "normalized" / f"{document_id}.txt").read_text(
        encoding="utf-8"
    )
    assert "行政执法监督文书" not in normalized_text
    assert "姓名：" not in normalized_text
    assert "单位：" not in normalized_text
    assert "PAGE" not in normalized_text

    structured = json.loads(
        (data_dir / "structured" / f"{document_id}.json").read_text(encoding="utf-8")
    )
    assert structured["content_class"] == "S3"
    assert structured["boundary_status"] == "confirmed"
    assert len(structured["articles"]) == EXPECTED_WS3_ARTICLE_COUNT

    with (data_dir / "chunks" / f"{document_id}.jsonl").open(
        encoding="utf-8"
    ) as handle:
        chunks = [json.loads(line) for line in handle]
    assert len(chunks) == EXPECTED_WS3_CHUNK_COUNT
    for chunk in chunks:
        assert chunk["document_id"] == document_id
        assert chunk["content_class"] == "S3"
        assert chunk["source_sha256"] == before_digest
        assert chunk["boundary_status"] == "confirmed"
        assert "行政执法监督文书" not in chunk["text"]
        assert "姓名：" not in chunk["text"]
        assert "单位：" not in chunk["text"]
        assert "PAGE" not in chunk["text"]

    keyword_rows_after = _count_keyword_rows(data_dir / "index" / "retrieval.db")
    vector_map_after = load_vector_map(data_dir / "index" / "vector_map.json")
    manifest_after = json.loads(
        (data_dir / "manifests" / "incremental_imports.json").read_text(
            encoding="utf-8"
        )
    )

    assert keyword_rows_after - keyword_rows_before == EXPECTED_WS3_CHUNK_COUNT
    assert len(vector_map_after) - len(vector_map_before) == EXPECTED_WS3_CHUNK_COUNT
    assert len(manifest_after["imports"]) - len(manifest_before["imports"]) == 1
    assert manifest_after["imports"][-1]["document_id"] == document_id
    assert manifest_after["imports"][-1]["chunk_count"] == EXPECTED_WS3_CHUNK_COUNT
    assert manifest_after["imports"][-1]["source_sha256"] == before_digest


def _count_keyword_rows(db_path: Path) -> int:
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])
