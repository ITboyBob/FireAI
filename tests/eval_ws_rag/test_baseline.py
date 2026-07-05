from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts.eval_ws_rag.baseline import (
    BaselineError,
    IncomparableRunsError,
    compare_runs,
    load_baseline,
    register_baseline,
)
from scripts.eval_ws_rag.report_models import (
    CitationRecord,
    DatasetIdentity,
    DocumentScorecard,
    EvaluationProtocol,
    EvaluationReport,
    EvaluatedSystem,
    FailureReason,
    JudgeDetail,
    JudgeResult,
    MetricScores,
    QuestionResult,
    RetrievedChunk,
    compute_protocol_fingerprint,
)
from scripts.eval_ws_rag.report_publisher import publish_run_atomic


def _make_protocol(answer_model: str = "doubao-1-5-lite-32k-250115") -> EvaluationProtocol:
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
            judge_repetitions=1,
            evidence_order_strategy="seed_shuffled",
            metric_algorithm_version="v1",
            thresholds=thresholds.as_dict(),
        ),
        judge_model="doubao-seed-2-1-pro-260628",
        judge_prompt_version="judge_v1",
        judge_repetitions=1,
        judge_calibrated=False,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
        answer_model=answer_model,
        answer_prompt_version="answer_v1",
        top_k=5,
    )


def _make_question(
    question_id: str,
    metrics: dict[str, float] | None = None,
) -> QuestionResult:
    if metrics is None:
        metrics = {
            "context_relevancy": 1.0,
            "source_coverage": 1.0,
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "citation_validity": 1.0,
            "refusal_appropriateness": 1.0,
        }
    return QuestionResult(
        question_id=question_id,
        question="问题？",
        question_type="frequent",
        answerable=True,
        expected_behavior="answer",
        expected_article="第一条",
        source_chunk_id="chunk_001",
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="chunk_001",
                document_id="doc_a",
                path="路径",
                text="文本",
                retrieval_score=0.9,
                keyword_score=0.8,
                vector_score=0.7,
                sources=["keyword"],
            )
        ],
        answer="答案。",
        citations=[CitationRecord(
            document_id="doc_a",
            path="路径",
            text="文本",
            matched_chunk_id="chunk_001",
            citation_label="路径",
        )],
        refused=False,
        uncertainty=None,
        metrics=MetricScores(**metrics),
        red_line_failures=[],
        failure_reasons=[],
        judge_result=JudgeResult(
            context_relevancy=metrics["context_relevancy"],
            faithfulness=metrics["faithfulness"],
            answer_relevance=metrics["answer_relevance"],
            details=[JudgeDetail(repetition=1)],
            prompt_version="judge_v1",
            model="doubao-seed-2-1-pro-260628",
        ),
        passed=True,
    )


def _make_scorecard(
    question_id: str,
    metrics: dict[str, float] | None = None,
) -> DocumentScorecard:
    q = _make_question(question_id, metrics)
    return DocumentScorecard(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha256",
        content_class="S1",
        question_count=1,
        passed_questions=1,
        failed_questions_count=0,
        red_line_failures_count=0,
        metrics=q.metrics,
        overall_pass_rate=1.0,
        failed_questions=[],
        questions=[q],
    )


def _make_report(
    run_id: str,
    metrics: dict[str, float] | None = None,
    answer_model: str = "doubao-1-5-lite-32k-250115",
) -> EvaluationReport:
    doc = _make_scorecard("q_001", metrics)
    return EvaluationReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(
            dataset_id="ds_001", dataset_fingerprint="fp_001", document_ids=["doc_a"]
        ),
        protocol=_make_protocol(answer_model=answer_model),
        system=EvaluatedSystem(
            git_commit="abc1234", git_dirty=False, corpus_fingerprint="cfp_001"
        ),
        summary=doc,
        documents=[doc],
    )


def _publish_run(tmp_path: Path, report: EvaluationReport) -> Path:
    from scripts.eval_ws_rag.report_models import ErrorReport

    errors = ErrorReport(
        schema_version="1.0.0",
        run_id=report.run_id,
        created_at=report.created_at,
        errors=[],
    )
    return publish_run_atomic(report, errors, tmp_path)


def test_register_baseline_loads_run_and_writes_registry(tmp_path: Path):
    run_dir = _publish_run(tmp_path / "runs", _make_report("run_001"))
    registry = tmp_path / "baselines.json"
    entry = register_baseline(name="baseline_v1", run_dir=run_dir, registry_path=registry)
    assert entry["run_path"] == str(run_dir)
    assert entry["dataset_id"] == "ds_001"
    assert registry.exists()


def test_register_rejects_overwrite(tmp_path: Path):
    run_dir = _publish_run(tmp_path / "runs", _make_report("run_001"))
    registry = tmp_path / "baselines.json"
    register_baseline(name="baseline_v1", run_dir=run_dir, registry_path=registry)
    with pytest.raises(FileExistsError):
        register_baseline(name="baseline_v1", run_dir=run_dir, registry_path=registry)


def test_register_replace_records_previous_run(tmp_path: Path):
    run1 = _publish_run(tmp_path / "runs", _make_report("run_001"))
    run2 = _publish_run(tmp_path / "runs", _make_report("run_002"))
    registry = tmp_path / "baselines.json"
    register_baseline(name="baseline_v1", run_dir=run1, registry_path=registry)
    entry = register_baseline(
        name="baseline_v1", run_dir=run2, registry_path=registry, replace=True
    )
    assert entry["run_path"] == str(run2)
    assert entry["previous_run_path"] == str(run1)


def test_register_rejects_missing_report(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(BaselineError):
        register_baseline(name="baseline_v1", run_dir=empty_dir, registry_path=tmp_path / "baselines.json")


def test_load_baseline_returns_entry(tmp_path: Path):
    run_dir = _publish_run(tmp_path / "runs", _make_report("run_001"))
    registry = tmp_path / "baselines.json"
    register_baseline(name="baseline_v1", run_dir=run_dir, registry_path=registry)
    entry = load_baseline(name="baseline_v1", registry_path=registry)
    assert entry["dataset_fingerprint"] == "fp_001"


def test_corrupt_registry_is_not_modified(tmp_path: Path):
    registry = tmp_path / "baselines.json"
    registry.write_text("not json", encoding="utf-8")
    run_dir = _publish_run(tmp_path / "runs", _make_report("run_001"))
    with pytest.raises(BaselineError):
        register_baseline(name="baseline_v1", run_dir=run_dir, registry_path=registry)


def test_compare_runs_reports_metric_deltas_and_win_rate(tmp_path: Path):
    baseline_dir = _publish_run(
        tmp_path / "runs",
        _make_report("run_baseline", metrics={
            "context_relevancy": 0.8,
            "source_coverage": 0.9,
            "faithfulness": 0.9,
            "answer_relevance": 0.8,
            "citation_validity": 1.0,
            "refusal_appropriateness": 0.9,
        }),
    )
    current_dir = _publish_run(
        tmp_path / "runs",
        _make_report("run_current", metrics={
            "context_relevancy": 1.0,
            "source_coverage": 1.0,
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "citation_validity": 1.0,
            "refusal_appropriateness": 1.0,
        }),
    )
    result = compare_runs(baseline_run_dir=baseline_dir, current_run_dir=current_dir)
    assert result["comparable"] is True
    assert result["win_rate"] == 1.0
    assert result["overall"]["wins"] == 1
    assert result["per_metric"]["context_relevancy"]["wins"] == 1
    assert result["per_question"][0]["outcome"] == "win"


def test_compare_runs_detects_tie(tmp_path: Path):
    baseline_dir = _publish_run(tmp_path / "runs", _make_report("run_baseline"))
    current_dir = _publish_run(tmp_path / "runs", _make_report("run_current"))
    result = compare_runs(baseline_run_dir=baseline_dir, current_run_dir=current_dir)
    assert result["overall"]["ties"] == 1
    assert result["win_rate"] == 0.0


def test_compare_runs_detects_loss(tmp_path: Path):
    baseline_dir = _publish_run(
        tmp_path / "runs",
        _make_report("run_baseline", metrics={
            "context_relevancy": 1.0,
            "source_coverage": 1.0,
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "citation_validity": 1.0,
            "refusal_appropriateness": 1.0,
        }),
    )
    current_dir = _publish_run(
        tmp_path / "runs",
        _make_report("run_current", metrics={
            "context_relevancy": 0.5,
            "source_coverage": 0.5,
            "faithfulness": 0.5,
            "answer_relevance": 0.5,
            "citation_validity": 1.0,
            "refusal_appropriateness": 0.5,
        }),
    )
    result = compare_runs(baseline_run_dir=baseline_dir, current_run_dir=current_dir)
    assert result["overall"]["losses"] == 1
    assert result["win_rate"] == 0.0


def test_compare_runs_rejects_different_dataset(tmp_path: Path):
    baseline = _make_report("run_baseline")
    current = _make_report("run_current")
    current.dataset.dataset_id = "ds_002"
    baseline_dir = _publish_run(tmp_path / "runs", baseline)
    current_dir = _publish_run(tmp_path / "runs", current)
    result = compare_runs(baseline_run_dir=baseline_dir, current_run_dir=current_dir)
    assert result["comparable"] is False
    assert "dataset_id" in result["reasons"][0]


def test_compare_runs_lists_system_diff(tmp_path: Path):
    baseline_dir = _publish_run(tmp_path / "runs", _make_report("run_baseline"))
    current_dir = _publish_run(
        tmp_path / "runs",
        _make_report("run_current", answer_model="different-model"),
    )
    result = compare_runs(baseline_run_dir=baseline_dir, current_run_dir=current_dir)
    diff_fields = {d["field"] for d in result["system_diff"]}
    assert "answer_model" in diff_fields


def test_compare_only_baseline_returns_waiting(tmp_path: Path, caplog):
    import logging

    from scripts.compare_ws_rag_runs import main as compare_main

    run_dir = _publish_run(tmp_path / "runs", _make_report("run_baseline"))
    with caplog.at_level(logging.INFO, logger="scripts.compare_ws_rag_runs"):
        code = compare_main(["--baseline-run", str(run_dir)])
    assert code == 0
    assert "等待 current Run" in caplog.text
