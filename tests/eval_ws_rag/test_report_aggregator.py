from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.eval_ws_rag.report_aggregator import aggregate_document, aggregate_run
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
)


def _make_question(
    question_id: str,
    passed: bool,
    red_lines: list[FailureReason] | None = None,
    metrics: dict[str, float] | None = None,
) -> QuestionResult:
    return QuestionResult(
        question_id=question_id,
        question="问题？",
        question_type="frequent",
        answerable=True,
        expected_behavior="answer",
        expected_article="第一条",
        source_chunk_id="chunk_001",
        retrieved_chunks=[],
        answer="答案。",
        citations=[],
        refused=False,
        uncertainty=None,
        metrics=MetricScores(**(metrics or {
            "context_relevancy": 1.0,
            "source_coverage": 1.0,
            "faithfulness": 1.0,
            "answer_relevance": 1.0,
            "citation_validity": 1.0,
            "refusal_appropriateness": 1.0,
        })),
        red_line_failures=red_lines or [],
        failure_reasons=[],
        judge_result=JudgeResult(
            context_relevancy=1.0,
            faithfulness=1.0,
            answer_relevance=1.0,
            details=[JudgeDetail(repetition=1)],
            prompt_version="judge_v1",
            model="doubao-seed-2-1-pro-260628",
        ),
        passed=passed,
    )


def test_aggregate_document_averages_metrics():
    q1 = _make_question("q_001", passed=True, metrics={
        "context_relevancy": 1.0,
        "source_coverage": 1.0,
        "faithfulness": 1.0,
        "answer_relevance": 0.8,
        "citation_validity": 1.0,
        "refusal_appropriateness": 1.0,
    })
    q2 = _make_question("q_002", passed=True, metrics={
        "context_relevancy": 0.6,
        "source_coverage": 0.8,
        "faithfulness": 0.8,
        "answer_relevance": 0.6,
        "citation_validity": 1.0,
        "refusal_appropriateness": 1.0,
    })
    scorecard = aggregate_document(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha256",
        content_class="S1",
        questions=[q1, q2],
    )
    assert scorecard.document_id == "doc_a"
    assert scorecard.question_count == 2
    assert scorecard.metrics.context_relevancy == pytest.approx(0.8)
    assert scorecard.metrics.answer_relevance == pytest.approx(0.7)


def test_aggregate_document_counts_failures():
    q1 = _make_question("q_001", passed=True)
    q2 = _make_question("q_002", passed=False, red_lines=[FailureReason(code="citation_invalid", description="")])
    scorecard = aggregate_document(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha256",
        content_class="S1",
        questions=[q1, q2],
    )
    assert scorecard.passed_questions == 1
    assert scorecard.failed_questions_count == 1
    assert scorecard.red_line_failures_count == 1
    assert scorecard.overall_pass_rate == pytest.approx(0.5)
    assert scorecard.failed_questions == ["q_002"]


def test_aggregate_run_weighted_by_questions():
    doc_a = aggregate_document(
        document_id="doc_a",
        title="法规A",
        source_sha256="sha1",
        content_class="S1",
        questions=[_make_question("q_a1", passed=True), _make_question("q_a2", passed=False)],
    )
    doc_b = aggregate_document(
        document_id="doc_b",
        title="法规B",
        source_sha256="sha2",
        content_class="S2",
        questions=[_make_question("q_b1", passed=False), _make_question("q_b2", passed=False), _make_question("q_b3", passed=False)],
    )
    report = aggregate_run(
        run_id="run_001",
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a", "doc_b"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        documents=[doc_a, doc_b],
    )
    # 2 questions in doc_a, 3 in doc_b; total 5; passed 1.
    assert report.summary.question_count == 5
    assert report.summary.passed_questions == 1
    assert report.summary.overall_pass_rate == pytest.approx(0.2)


def test_aggregate_run_rejects_zero_questions():
    with pytest.raises(ValueError, match="no questions"):
        aggregate_run(
            run_id="run_001",
            created_at=datetime.now(timezone.utc),
            dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a"]),
            protocol=_make_protocol(),
            system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
            documents=[],
        )


def test_aggregate_run_stable_document_order():
    doc_b = aggregate_document(
        document_id="doc_b",
        title="法规B",
        source_sha256="sha2",
        content_class="S2",
        questions=[_make_question("q_b1", passed=True)],
    )
    doc_a = aggregate_document(
        document_id="doc_a",
        title="法规A",
        source_sha256="sha1",
        content_class="S1",
        questions=[_make_question("q_a1", passed=True)],
    )
    report = aggregate_run(
        run_id="run_001",
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a", "doc_b"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        documents=[doc_b, doc_a],
    )
    ids = [d.document_id for d in report.documents]
    assert ids == ["doc_a", "doc_b"]


def test_aggregate_run_validates_with_report_model():
    doc = aggregate_document(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha1",
        content_class="S1",
        questions=[_make_question("q_001", passed=True)],
    )
    report = aggregate_run(
        run_id="run_001",
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        documents=[doc],
    )
    assert isinstance(report, EvaluationReport)
    assert report.summary.question_count == 1


def test_aggregate_run_cross_field_consistency():
    doc = aggregate_document(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha1",
        content_class="S1",
        questions=[_make_question("q_001", passed=True)],
    )
    report = aggregate_run(
        run_id="run_001",
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_001", dataset_fingerprint="fp", document_ids=["doc_a"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        documents=[doc],
    )
    assert report.dataset.dataset_id == "ds_001"
    assert report.protocol.judge_model == "doubao-seed-2-1-pro-260628"
    assert report.system.git_commit == "abc"


def test_ws_fixture_aggregation():
    doc = aggregate_document(
        document_id="doc_d97773f1500c",
        title="消防监督检查规定",
        source_sha256="sha1",
        content_class="S1",
        questions=[
            _make_question("q_frequent_001", passed=True),
            _make_question("q_boundary_001", passed=False, red_lines=[FailureReason(code="citation_invalid", description="")]),
        ],
    )
    report = aggregate_run(
        run_id="run_ws_001",
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(dataset_id="ds_ws", dataset_fingerprint="fp", document_ids=["doc_d97773f1500c"]),
        protocol=_make_protocol(),
        system=EvaluatedSystem(git_commit="abc", git_dirty=False, corpus_fingerprint="cfp"),
        documents=[doc],
    )
    assert report.summary.question_count == 2
    assert report.summary.passed_questions == 1
    assert report.summary.failed_questions_count == 1


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
