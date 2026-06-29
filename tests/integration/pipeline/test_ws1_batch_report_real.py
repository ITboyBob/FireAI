import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_ingestion_batch import (
    BatchFileResult,
    FileState,
    save_batch_report,
)


TODO_BASELINE_PATH = Path("tests/fixtures/legal_ingestion/todo_baseline.json")
SOURCE_ROOT = Path("法律文本/todo")


def _load_baseline():
    data = json.loads(TODO_BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in data
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S1"
    ]


def _source_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_ws1_baseline_selects_exactly_eight():
    cases = _load_baseline()
    assert len(cases) == 8


def test_ws1_source_files_exist_and_match_baseline(tmp_path):
    cases = _load_baseline()
    source_digests: dict[str, str] = {}
    for item in cases:
        relative_path = item["relative_path"]
        source_path = SOURCE_ROOT / relative_path
        assert source_path.exists(), f"源文件缺失: {relative_path}"
        digest = _source_sha256(source_path)
        source_digests[relative_path] = digest

    results = tuple(
        BatchFileResult(
            relative_path=item["relative_path"],
            source_sha256=source_digests[item["relative_path"]],
            document_id=f"doc_{index}",
            attempt_id="attempt-1",
            final_state=FileState.DISCOVERED,
        )
        for index, item in enumerate(cases)
    )
    report_path = tmp_path / "batch.json"
    report = save_batch_report(
        report_path,
        batch_id="ws1-batch-report-1",
        source_root=SOURCE_ROOT.resolve(),
        results=results,
    )

    assert report_path.exists()
    loaded = save_batch_report.load(report_path)
    assert loaded.batch_id == report.batch_id
    assert len(loaded.results) == 8
    assert loaded.overall_status == "completed"
    assert loaded.summary["discovered"] == 8

    for item in cases:
        after_digest = _source_sha256(SOURCE_ROOT / item["relative_path"])
        assert after_digest == source_digests[item["relative_path"]]
