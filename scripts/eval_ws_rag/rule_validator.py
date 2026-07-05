from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.eval_ws_rag.dataset_models import DatasetQuestion
from scripts.eval_ws_rag.llm_judge import JudgeResult
from scripts.eval_ws_rag.report_models import CitationRecord, FailureReason, MetricScores, RetrievedChunk


class RedLineCode:
    CITATION_INVALID = "citation_invalid"
    OUT_OF_SCOPE_CONTENT = "out_of_scope_content"
    MISSING_REQUIRED_REFUSAL = "missing_required_refusal"


@dataclass
class RuleValidationResult:
    metrics: MetricScores
    red_line_failures: list[FailureReason]
    failure_reasons: list[FailureReason]
    passed: bool


def validate_rules(
    *,
    retrieved_chunks: list[RetrievedChunk],
    answer: str,
    citations: list[CitationRecord],
    refused: bool,
    uncertainty: str | None,
    dataset_question: DatasetQuestion,
    judge_result: JudgeResult,
    thresholds: dict[str, float],
) -> RuleValidationResult:
    """Apply rule-based validation and threshold checks to one question result.

    Mutates retrieved_chunks to set `cited=True` for chunks matched by citations.
    """
    red_lines: list[FailureReason] = []

    # 1. Citation validity and binding.
    citation_validity = _compute_citation_validity(
        citations=citations,
        retrieved_chunks=retrieved_chunks,
        answerable=dataset_question.answerable,
        refused=refused,
        red_lines=red_lines,
    )

    # 2. Source coverage.
    source_coverage = _compute_source_coverage(
        retrieved_chunks=retrieved_chunks,
        expected_article=dataset_question.expected_article,
    )

    # 3. Refusal appropriateness.
    refusal_appropriateness = _compute_refusal_appropriateness(
        answerable=dataset_question.answerable,
        expected_behavior=dataset_question.expected_behavior,
        refused=refused,
        red_lines=red_lines,
    )

    # 4. Out-of-scope content red line from Judge claim verdicts.
    if judge_result and _has_out_of_scope_claim(judge_result):
        red_lines.append(
            FailureReason(
                code=RedLineCode.OUT_OF_SCOPE_CONTENT,
                description="答案包含当前文件外且无证据支持的内容",
            )
        )

    metrics = MetricScores(
        context_relevancy=judge_result.context_relevancy if judge_result else 0.0,
        source_coverage=source_coverage,
        faithfulness=judge_result.faithfulness if judge_result else 0.0,
        answer_relevance=judge_result.answer_relevance if judge_result else 0.0,
        citation_validity=citation_validity,
        refusal_appropriateness=refusal_appropriateness,
    )

    passed = _decide_question_pass(metrics, red_lines, thresholds)

    failure_reasons = _build_failure_reasons(metrics, red_lines, thresholds)

    return RuleValidationResult(
        metrics=metrics,
        red_line_failures=red_lines,
        failure_reasons=failure_reasons,
        passed=passed,
    )


def _compute_citation_validity(
    *,
    citations: list[CitationRecord],
    retrieved_chunks: list[RetrievedChunk],
    answerable: bool,
    refused: bool,
    red_lines: list[FailureReason],
) -> float:
    if not answerable and refused:
        # Correct refusal: no citation needed, validity is 1.0.
        return 1.0

    if answerable and not citations:
        # Answerable question must have citations.
        return 0.0

    valid_count = 0
    chunk_by_id = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    for citation in citations:
        matched = chunk_by_id.get(citation.matched_chunk_id)
        if matched is None:
            red_lines.append(
                FailureReason(
                    code=RedLineCode.CITATION_INVALID,
                    description=f"引文无法绑定到检索证据：{citation.citation_label}",
                )
            )
            continue
        if matched.path != citation.path and matched.text != citation.text:
            red_lines.append(
                FailureReason(
                    code=RedLineCode.CITATION_INVALID,
                    description=f"引文与检索证据内容不一致：{citation.citation_label}",
                )
            )
            continue
        matched.cited = True
        valid_count += 1

    return valid_count / len(citations) if citations else 1.0


def _compute_source_coverage(
    *,
    retrieved_chunks: list[RetrievedChunk],
    expected_article: str | None,
) -> float:
    if not expected_article:
        return 1.0
    article_nos = {chunk.article_no for chunk in retrieved_chunks if chunk.article_no}
    return 1.0 if expected_article in article_nos else 0.0


def _compute_refusal_appropriateness(
    *,
    answerable: bool,
    expected_behavior: str,
    refused: bool,
    red_lines: list[FailureReason],
) -> float:
    if answerable and expected_behavior == "answer" and refused:
        red_lines.append(
            FailureReason(
                code=RedLineCode.MISSING_REQUIRED_REFUSAL,
                description="可回答问题未给出结论",
            )
        )
        return 0.0
    if not answerable and expected_behavior == "refuse" and not refused:
        red_lines.append(
            FailureReason(
                code=RedLineCode.MISSING_REQUIRED_REFUSAL,
                description="不可回答问题未正确拒答",
            )
        )
        return 0.0
    return 1.0


def _has_out_of_scope_claim(judge_result: JudgeResult) -> bool:
    for detail in judge_result.details:
        if detail.claims_verdict:
            if any(verdict == "not_supported" for verdict in detail.claims_verdict):
                return True
    return False


def _decide_question_pass(
    metrics: MetricScores,
    red_lines: list[FailureReason],
    thresholds: dict[str, float],
) -> bool:
    if red_lines:
        return False
    return (
        metrics.context_relevancy >= thresholds["context_relevancy"]
        and metrics.source_coverage >= thresholds["source_coverage"]
        and metrics.faithfulness >= thresholds["faithfulness"]
        and metrics.answer_relevance >= thresholds["answer_relevance"]
        and metrics.citation_validity >= thresholds["citation_validity"]
        and metrics.refusal_appropriateness >= thresholds["refusal_appropriateness"]
    )


def _build_failure_reasons(
    metrics: MetricScores,
    red_lines: list[FailureReason],
    thresholds: dict[str, float],
) -> list[FailureReason]:
    reasons = list(red_lines)
    checks = [
        ("context_relevancy", metrics.context_relevancy, "上下文相关性低于阈值"),
        ("source_coverage", metrics.source_coverage, "来源覆盖率低于阈值"),
        ("faithfulness", metrics.faithfulness, "忠实度低于阈值"),
        ("answer_relevance", metrics.answer_relevance, "答案相关性低于阈值"),
        ("citation_validity", metrics.citation_validity, "引文有效性低于阈值"),
        ("refusal_appropriateness", metrics.refusal_appropriateness, "拒答适当性低于阈值"),
    ]
    for key, value, description in checks:
        if value < thresholds[key]:
            reasons.append(
                FailureReason(
                    code=f"threshold_{key}",
                    description=f"{description}: {value:.4f} < {thresholds[key]}",
                )
            )
    return reasons
