from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from scripts.eval_ws_rag.report_models import (
    DatasetIdentity,
    DocumentScorecard,
    EvaluationProtocol,
    EvaluationReport,
    EvaluatedSystem,
    MetricScores,
    QuestionResult,
)


def aggregate_document(
    *,
    document_id: str,
    title: str,
    source_sha256: str,
    content_class: str,
    questions: Sequence[QuestionResult],
) -> DocumentScorecard:
    """Aggregate question-level results into a per-document scorecard."""
    if not questions:
        raise ValueError(f"document {document_id} has no questions")

    metrics = _average_metrics(questions)
    passed_questions = sum(1 for q in questions if q.passed)
    failed_questions = len(questions) - passed_questions
    red_line_failures = sum(len(q.red_line_failures) for q in questions)
    failed_question_ids = [q.question_id for q in questions if not q.passed]

    return DocumentScorecard(
        document_id=document_id,
        title=title,
        source_sha256=source_sha256,
        content_class=content_class,
        question_count=len(questions),
        passed_questions=passed_questions,
        failed_questions_count=failed_questions,
        red_line_failures_count=red_line_failures,
        metrics=metrics,
        overall_pass_rate=passed_questions / len(questions),
        failed_questions=failed_question_ids,
        questions=list(questions),
    )


def aggregate_run(
    *,
    run_id: str,
    created_at: datetime,
    dataset: DatasetIdentity,
    protocol: EvaluationProtocol,
    system: EvaluatedSystem,
    documents: Sequence[DocumentScorecard],
) -> EvaluationReport:
    """Aggregate document scorecards into a run-level EvaluationReport."""
    if not documents:
        raise ValueError("aggregate_run: no questions")

    total_questions = sum(doc.question_count for doc in documents)
    if total_questions == 0:
        raise ValueError("aggregate_run: no questions")

    passed_questions = sum(doc.passed_questions or 0 for doc in documents)
    failed_questions = sum(doc.failed_questions_count or 0 for doc in documents)
    red_line_failures = sum(doc.red_line_failures_count or 0 for doc in documents)
    overall_pass_rate = passed_questions / total_questions

    summary_failed_questions: list[str] = []
    for doc in documents:
        summary_failed_questions.extend(doc.failed_questions)

    # Weighted average across documents by question count.
    summary_metrics = _weighted_average_metrics(documents)

    sorted_documents = sorted(documents, key=lambda d: d.document_id)

    summary = DocumentScorecard(
        document_id="__summary__",
        title="总体统计",
        source_sha256="",
        content_class=None,
        question_count=total_questions,
        passed_questions=passed_questions,
        failed_questions_count=failed_questions,
        red_line_failures_count=red_line_failures,
        metrics=summary_metrics,
        overall_pass_rate=overall_pass_rate,
        failed_questions=summary_failed_questions,
        questions=[],
    )

    return EvaluationReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=created_at,
        dataset=dataset,
        protocol=protocol,
        system=system,
        summary=summary,
        documents=sorted_documents,
    )


def _average_metrics(questions: Sequence[QuestionResult]) -> MetricScores:
    if not questions:
        return MetricScores(
            context_relevancy=0.0,
            source_coverage=0.0,
            faithfulness=0.0,
            answer_relevance=0.0,
            citation_validity=0.0,
            refusal_appropriateness=0.0,
        )
    fields = [
        "context_relevancy",
        "source_coverage",
        "faithfulness",
        "answer_relevance",
        "citation_validity",
        "refusal_appropriateness",
    ]
    averages = {field: sum(getattr(q.metrics, field) for q in questions) / len(questions) for field in fields}
    return MetricScores(**averages)


def _weighted_average_metrics(documents: Sequence[DocumentScorecard]) -> MetricScores:
    fields = [
        "context_relevancy",
        "source_coverage",
        "faithfulness",
        "answer_relevance",
        "citation_validity",
        "refusal_appropriateness",
    ]
    total_questions = sum(doc.question_count for doc in documents)
    if total_questions == 0:
        return MetricScores(
            context_relevancy=0.0,
            source_coverage=0.0,
            faithfulness=0.0,
            answer_relevance=0.0,
            citation_validity=0.0,
            refusal_appropriateness=0.0,
        )
    weighted = {}
    for field in fields:
        weighted_sum = sum(
            getattr(doc.metrics, field) * doc.question_count for doc in documents
        )
        weighted[field] = weighted_sum / total_questions
    return MetricScores(**weighted)
