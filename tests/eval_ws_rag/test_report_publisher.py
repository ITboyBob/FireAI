from __future__ import annotations

import json
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.eval_ws_rag.report_models import DatasetIdentity, ErrorReport, EvaluationProtocol, EvaluationReport, EvaluatedSystem, MetricScores
from scripts.eval_ws_rag.report_publisher import FileLock, publish_run_atomic


def _make_protocol() -> EvaluationProtocol:
    from scripts.eval_ws_rag.report_models import compute_protocol_fingerprint
    thresholds = MetricScores(
        context_relevancy=0.8,
        source_coverage=0.9,
        faithfulness=0.9,
        answer_relevance=0.8,
        citation_validity=1.0,
        refusal_appropriateness=0.9,
    )
    return EvaluationProtocol(
        protocol_fingerprint=compute_protocol_fingerprint(
            judge_model="doubao-seed-2-1-pro-260628",
            judge_prompt_version="judge_v1",
            judge_repetitions=3,
            evidence_order_strategy="seed_shuffled",
            metric_algorithm_version="v1",
            thresholds=thresholds.as_dict(),
        ),
        judge_model="doubao-seed-2-1-pro-260628",
        judge_prompt_version="judge_v1",
        judge_repetitions=3,
        judge_calibrated=False,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
        answer_model="doubao-1-5-lite-32k-250115",
        answer_prompt_version="answer_v1",
        top_k=5,
    )


def _make_report(run_id: str) -> EvaluationReport:
    return EvaluationReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        summary={
            "document_id": "__summary__",
            "title": "总体统计",
            "question_count": 0,
            "passed_questions": 0,
            "failed_questions_count": 0,
            "red_line_failures_count": 0,
            "metrics": {
                "context_relevancy": 1.0,
                "source_coverage": 1.0,
                "faithfulness": 1.0,
                "answer_relevance": 1.0,
                "citation_validity": 1.0,
                "refusal_appropriateness": 1.0,
            },
            "overall_pass_rate": 1.0,
            "failed_questions": [],
            "questions": [],
        },
        documents=[],
    )


def _make_errors(run_id: str, created_at: datetime | None = None) -> ErrorReport:
    return ErrorReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=created_at if created_at is not None else datetime.now(timezone.utc),
        errors=[],
    )


def test_publishes_both_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = _make_report("run_001")
        errors = _make_errors("run_001", report.created_at)

        run_dir = publish_run_atomic(report, errors, root)

        assert run_dir.exists()
        assert (run_dir / "report.json").exists()
        assert (run_dir / "errors.json").exists()
        data = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        assert data["run_id"] == "run_001"


def test_refuses_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = _make_report("run_001")
        errors = _make_errors("run_001", report.created_at)
        publish_run_atomic(report, errors, root)

        with pytest.raises(FileExistsError):
            publish_run_atomic(report, errors, root)


def test_rejects_header_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = _make_report("run_001")
        errors = _make_errors("run_002", report.created_at)

        with pytest.raises(ValueError, match="run_id mismatch"):
            publish_run_atomic(report, errors, root)


def test_failed_second_file_leaves_no_run():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = _make_report("run_001")
        errors = _make_errors("run_001", report.created_at)

        def bad_factory(path):
            raise RuntimeError("lock failure")

        with pytest.raises(RuntimeError):
            publish_run_atomic(report, errors, root, lock_factory=bad_factory)

        assert not (root / "run_001").exists()
        assert len(list(root.glob(".*.tmp*"))) == 0


def test_directory_publish_is_atomic():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = _make_report("run_001")
        errors = _make_errors("run_001", report.created_at)

        publish_run_atomic(report, errors, root)

        runs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        assert runs == [root / "run_001"]
        assert set(f.name for f in runs[0].iterdir()) == {"report.json", "errors.json"}


def test_file_lock_serializes_publishers(tmp_path):
    lock_path = tmp_path / "test.lock"
    results = []

    def worker():
        # Each publisher holds its own FileLock instance, but the same file path serializes them.
        with FileLock(lock_path):
            time.sleep(0.05)
            results.append(threading.current_thread().name)

    t1 = threading.Thread(target=worker, name="t1")
    t2 = threading.Thread(target=worker, name="t2")
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
