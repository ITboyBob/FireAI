from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.evaluate_ws_rag import main as cli_main
from scripts.eval_ws_rag.orchestrator import RunResult
from scripts.eval_ws_rag.report_models import compute_protocol_fingerprint


def test_cli_requires_dataset():
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--run-id", "run_001"])
    assert exc_info.value.code == 2


def test_cli_requires_run_id():
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--dataset", "dataset.json"])
    assert exc_info.value.code == 2


def test_cli_runs_successfully(monkeypatch, tmp_path: Path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("{}", encoding="utf-8")
    reports_root = tmp_path / "reports"
    run_dir = reports_root / "run_001"

    def fake_run_evaluation(**kwargs: Any) -> RunResult:
        assert kwargs["dataset_path"] == dataset_path
        assert kwargs["run_id"] == "run_001"
        assert kwargs["data_dir"] == Path("data")
        assert kwargs["reports_root"] == reports_root
        # Build a minimal report-like object for logging.
        from scripts.eval_ws_rag.report_models import (
            DatasetIdentity,
            EvaluationProtocol,
            EvaluationReport,
            EvaluatedSystem,
            MetricScores,
        )

        thresholds = MetricScores(
            context_relevancy=1.0,
            source_coverage=1.0,
            faithfulness=1.0,
            answer_relevance=1.0,
            citation_validity=1.0,
            refusal_appropriateness=1.0,
        )
        protocol = EvaluationProtocol(
            protocol_fingerprint=compute_protocol_fingerprint(
                judge_model="judge",
                judge_prompt_version="judge_v1",
                judge_repetitions=1,
                evidence_order_strategy="seed_shuffled",
                metric_algorithm_version="v1",
                thresholds=thresholds.as_dict(),
            ),
            judge_model="judge",
            judge_prompt_version="judge_v1",
            judge_repetitions=1,
            judge_calibrated=False,
            evidence_order_strategy="seed_shuffled",
            metric_algorithm_version="v1",
            thresholds=thresholds,
            answer_model="answer",
            answer_prompt_version="answer_v1",
            top_k=5,
        )
        report = EvaluationReport(
            schema_version="1.0.0",
            run_id="run_001",
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a"]),
            protocol=protocol,
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
        return RunResult(run_dir=run_dir, report=report, errors=None)

    monkeypatch.setenv("CHAT_MODEL", "doubao-1-5-lite-32k-250115")
    monkeypatch.setenv("WS_RAG_JUDGE_MODEL", "doubao-seed-2-1-pro-260628")
    monkeypatch.setattr("scripts.evaluate_ws_rag.run_evaluation", fake_run_evaluation)

    code = cli_main([
        "--dataset", str(dataset_path),
        "--run-id", "run_001",
        "--reports-root", str(reports_root),
    ])
    assert code == 0


def test_cli_fatal_failure_returns_one(monkeypatch, tmp_path: Path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("{}", encoding="utf-8")

    def fake_run_evaluation(**kwargs: Any) -> None:
        from scripts.eval_ws_rag.orchestrator import FatalEvaluationError
        from scripts.eval_ws_rag.report_models import EvaluationError

        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="索引文件缺失",
                error_type="FileNotFoundError",
                message="missing index",
                recoverable=False,
            )
        )

    monkeypatch.setenv("CHAT_MODEL", "doubao-1-5-lite-32k-250115")
    monkeypatch.setenv("WS_RAG_JUDGE_MODEL", "doubao-seed-2-1-pro-260628")
    monkeypatch.setattr("scripts.evaluate_ws_rag.run_evaluation", fake_run_evaluation)

    code = cli_main([
        "--dataset", str(dataset_path),
        "--run-id", "run_001",
        "--reports-root", str(tmp_path / "reports"),
    ])
    assert code == 1
