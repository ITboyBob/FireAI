from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.eval_ws_rag.dataset_models import DatasetQuestion
from scripts.eval_ws_rag.llm_judge import JudgeDetail, JudgeResult
from scripts.eval_ws_rag.report_models import CitationRecord, RetrievedChunk
from scripts.eval_ws_rag.rule_validator import (
    RedLineCode,
    RuleValidationResult,
    validate_rules,
)


def _make_chunk(
    chunk_id: str, document_id: str, article_no: str | None = None, text: str = "文本"
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        path=f"路径 > {article_no or '第一条'}",
        text=text,
        article_no=article_no,
        retrieval_score=0.9,
        keyword_score=0.8,
        vector_score=0.7,
        sources=["keyword"],
    )


def _make_dataset_question(
    *,
    answerable: bool = True,
    expected_behavior: str = "answer",
    expected_article: str | None = "第一条",
) -> DatasetQuestion:
    return DatasetQuestion(
        question_id="q_001",
        question="问题？",
        question_type="frequent",
        answerable=answerable,
        expected_behavior=expected_behavior,
        expected_article=expected_article,
        source_chunk_id="chunk_001",
        answer_sketch="摘要",
    )


def _make_judge_result(
    context_relevancy: float = 1.0,
    faithfulness: float = 1.0,
    answer_relevance: float = 1.0,
) -> JudgeResult:
    return JudgeResult(
        context_relevancy=context_relevancy,
        faithfulness=faithfulness,
        answer_relevance=answer_relevance,
        details=[
            JudgeDetail(
                repetition=1,
                context_helpful=[True],
                claims_verdict=["supported"],
                answer_relevance_likert=5,
            )
        ],
        prompt_version="judge_v1",
        model="doubao-seed-2-1-pro-260628",
    )


def _thresholds() -> dict[str, float]:
    return {
        "context_relevancy": 0.8,
        "source_coverage": 0.9,
        "faithfulness": 0.9,
        "answer_relevance": 0.8,
        "citation_validity": 1.0,
        "refusal_appropriateness": 0.9,
    }


def test_citation_binds_to_retrieved_chunk():
    chunks = [_make_chunk("chunk_001", "doc_a", "第一条")]
    citations = [CitationRecord(
        document_id="doc_a",
        path="路径 > 第一条",
        text="文本",
        matched_chunk_id="chunk_001",
        citation_label="路径 > 第一条",
    )]
    result = validate_rules(
        retrieved_chunks=chunks,
        answer="答案。",
        citations=citations,
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.citation_validity == 1.0
    assert chunks[0].cited is True


def test_invalid_citation_records_red_line():
    chunks = [_make_chunk("chunk_001", "doc_a", "第一条")]
    citations = [CitationRecord(
        document_id="doc_a",
        path="路径 > 不存在的条",
        text="文本",
        matched_chunk_id="",
        citation_label="路径 > 不存在的条",
    )]
    result = validate_rules(
        retrieved_chunks=chunks,
        answer="答案。",
        citations=citations,
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert any(f.code == RedLineCode.CITATION_INVALID for f in result.red_line_failures)
    assert result.passed is False


def test_source_coverage_passes_when_expected_article_found():
    chunks = [_make_chunk("chunk_001", "doc_a", "第一条")]
    result = validate_rules(
        retrieved_chunks=chunks,
        answer="答案。",
        citations=[],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(expected_article="第一条"),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.source_coverage == 1.0


def test_source_coverage_fails_when_expected_article_missing():
    chunks = [_make_chunk("chunk_001", "doc_a", "第二条")]
    result = validate_rules(
        retrieved_chunks=chunks,
        answer="答案。",
        citations=[],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(expected_article="第一条"),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.source_coverage == 0.0


def test_answerable_question_refusal_fails():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="证据不足，无法可靠回答。",
        citations=[],
        refused=True,
        uncertainty="",
        dataset_question=_make_dataset_question(answerable=True, expected_behavior="answer"),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert any(f.code == RedLineCode.MISSING_REQUIRED_REFUSAL for f in result.red_line_failures)
    assert result.metrics.refusal_appropriateness == 0.0


def test_unanswerable_question_answered_fails():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="这是答案。",
        citations=[],
        refused=False,
        uncertainty="",
        dataset_question=_make_dataset_question(
            answerable=False, expected_behavior="refuse", expected_article=None
        ),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert any(f.code == RedLineCode.MISSING_REQUIRED_REFUSAL for f in result.red_line_failures)


def test_out_of_scope_content_red_line():
    chunks = [_make_chunk("chunk_001", "doc_a", "第一条")]
    judge = _make_judge_result()
    judge.details[0].claims_verdict = ["not_supported"]
    result = validate_rules(
        retrieved_chunks=chunks,
        answer="这是文件外杜撰内容。",
        citations=[],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=judge,
        thresholds=_thresholds(),
    )
    assert any(f.code == RedLineCode.OUT_OF_SCOPE_CONTENT for f in result.red_line_failures)


def test_citation_validity_for_correct_refusal():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="证据不足，无法可靠回答。",
        citations=[],
        refused=True,
        uncertainty="",
        dataset_question=_make_dataset_question(
            answerable=False, expected_behavior="refuse", expected_article=None
        ),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.citation_validity == 1.0


def test_citation_validity_for_answerable_without_citation():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="答案。",
        citations=[],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.citation_validity == 0.0


def test_all_thresholds_pass_and_no_red_lines():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="答案。",
        citations=[CitationRecord(
            document_id="doc_a",
            path="路径 > 第一条",
            text="文本",
            matched_chunk_id="chunk_001",
            citation_label="路径 > 第一条",
        )],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.passed is True
    assert result.metrics.context_relevancy == 1.0


def test_context_relevancy_below_threshold_fails():
    result = validate_rules(
        retrieved_chunks=[_make_chunk("chunk_001", "doc_a", "第一条")],
        answer="答案。",
        citations=[],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(),
        judge_result=_make_judge_result(context_relevancy=0.5),
        thresholds=_thresholds(),
    )
    assert result.passed is False
    assert result.metrics.context_relevancy == 0.5


def test_real_chunk_citation_binding():
    chunk_path = Path("data/chunks/doc_d97773f1500c.jsonl")
    if not chunk_path.exists():
        pytest.skip("真实 chunk 不存在")

    import json
    chunk_data = json.loads(chunk_path.read_text(encoding="utf-8").splitlines()[0])
    chunk = RetrievedChunk(
        chunk_id=chunk_data["chunk_id"],
        document_id=chunk_data["document_id"],
        path=chunk_data["path"],
        text=chunk_data["text"],
        article_no=chunk_data.get("article_no"),
        retrieval_score=0.9,
        keyword_score=0.8,
        vector_score=0.7,
        sources=["keyword"],
    )
    citation = CitationRecord(
        document_id=chunk_data["document_id"],
        path=chunk_data["path"],
        text=chunk_data["text"],
        matched_chunk_id=chunk_data["chunk_id"],
        citation_label=chunk_data["path"],
    )
    result = validate_rules(
        retrieved_chunks=[chunk],
        answer="答案。",
        citations=[citation],
        refused=False,
        uncertainty=None,
        dataset_question=_make_dataset_question(expected_article=chunk_data.get("article_no")),
        judge_result=_make_judge_result(),
        thresholds=_thresholds(),
    )
    assert result.metrics.citation_validity == 1.0
    assert chunk.cited is True
