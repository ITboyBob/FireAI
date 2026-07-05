from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.eval_ws_rag.eval_chat_client import (
    ContextJudgment,
    FaithfulnessJudgment,
    RelevanceJudgment,
    StructuredEvalClient,
)
from scripts.eval_ws_rag.llm_judge import JudgeError, JudgeResult, score_question


def _fake_complete_responses(responses: list[dict[str, Any]]):
    """Return a fake complete that cycles through responses based on response_model."""
    call_index = 0

    def complete(messages: list[dict[str, str]], response_model: type) -> Any:
        nonlocal call_index
        response = responses[call_index % len(responses)]
        call_index += 1
        return response_model.model_validate(response)

    return complete


def _make_client():
    # Order of calls in score_question: context, faithfulness, relevance per repetition.
    responses = [
        # repetition 1
        {"helpful": [True, True, False]},
        {"claims_verdict": ["supported", "not_supported"]},
        {"relevance_likert": 4},
        # repetition 2
        {"helpful": [True, False, False]},
        {"claims_verdict": ["supported", "supported"]},
        {"relevance_likert": 3},
        # repetition 3
        {"helpful": [True, True, True]},
        {"claims_verdict": ["supported"]},
        {"relevance_likert": 5},
    ]
    return StructuredEvalClient(complete=_fake_complete_responses(responses))


def _make_chunks() -> list[dict[str, Any]]:
    return [
        {"chunk_id": "chunk_001", "text": "片段一"},
        {"chunk_id": "chunk_002", "text": "片段二"},
        {"chunk_id": "chunk_003", "text": "片段三"},
    ]


def test_score_question_averages_three_repetitions():
    client = _make_client()
    result = score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=_make_chunks(),
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    assert isinstance(result, JudgeResult)
    # context_relevancy: (2 + 1 + 3) / 3 / 3 = 6/9 = 0.666...
    assert result.context_relevancy == pytest.approx(2 / 3, abs=1e-6)
    # faithfulness: (1/2 + 1 + 1) / 3 = (0.5 + 1 + 1) / 3 = 0.8333...
    assert result.faithfulness == pytest.approx(2.5 / 3, abs=1e-6)
    # answer_relevance: (4 + 3 + 5) / 3 / 5 = 12 / 15 = 0.8
    assert result.answer_relevance == pytest.approx(0.8, abs=1e-6)
    assert len(result.details) == 3


def test_score_question_keeps_raw_details():
    client = _make_client()
    result = score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=_make_chunks(),
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    assert result.details[0].context_helpful == [True, True, False]
    assert result.details[1].claims_verdict == ["supported", "supported"]
    assert result.details[2].answer_relevance_likert == 5


def test_score_question_shuffles_order_differently_per_repetition():
    orders: list[tuple[str, ...]] = []

    def capturing_complete(messages: list[dict[str, str]], response_model: type) -> Any:
        content = messages[-1]["content"]
        # Extract chunk_id list from the prompt.
        chunk_ids: list[str] = []
        for line in content.splitlines():
            if line.startswith("- chunk_id: "):
                chunk_ids.append(line.split("- chunk_id: ", 1)[1].strip())
        if response_model is ContextJudgment:
            orders.append(tuple(chunk_ids))
            return ContextJudgment(helpful=[True] * len(chunk_ids))
        if response_model is FaithfulnessJudgment:
            return FaithfulnessJudgment(claims_verdict=["supported"])
        return RelevanceJudgment(relevance_likert=4)

    client = StructuredEvalClient(complete=capturing_complete)
    score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=_make_chunks(),
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    assert len(orders) == 3
    # With three chunks and deterministic seeding, repetitions should differ.
    assert len(set(orders)) == 3


def test_score_question_reproducible_with_same_seed():
    client = _make_client()
    result1 = score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=_make_chunks(),
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    result2 = score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=_make_chunks(),
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    assert result1.context_relevancy == result2.context_relevancy
    assert result1.faithfulness == result2.faithfulness
    assert result1.answer_relevance == result2.answer_relevance


def test_score_question_serial_no_concurrency():
    active: list[int] = []
    max_active = 0

    def tracking_complete(messages: list[dict[str, str]], response_model: type) -> Any:
        nonlocal max_active
        active.append(1)
        max_active = max(max_active, len(active))
        result: Any
        if response_model is ContextJudgment:
            result = ContextJudgment(helpful=[True])
        elif response_model is FaithfulnessJudgment:
            result = FaithfulnessJudgment(claims_verdict=["supported"])
        else:
            result = RelevanceJudgment(relevance_likert=4)
        active.pop()
        return result

    client = StructuredEvalClient(complete=tracking_complete)
    score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=[{"chunk_id": "c1", "text": "t"}],
        repetitions=3,
        seed=42,
        question_id="q_001",
    )
    assert max_active == 1


def test_score_question_hides_version_name():
    captured: list[str] = []

    def capture_complete(messages: list[dict[str, str]], response_model: type) -> Any:
        captured.append(messages[-1]["content"])
        if response_model is ContextJudgment:
            return ContextJudgment(helpful=[True])
        if response_model is FaithfulnessJudgment:
            return FaithfulnessJudgment(claims_verdict=["supported"])
        return RelevanceJudgment(relevance_likert=4)

    client = StructuredEvalClient(complete=capture_complete)
    score_question(
        client=client,
        question="问题？",
        answer="答案。",
        chunks=[{"chunk_id": "c1", "text": "t"}],
        repetitions=1,
        seed=42,
        question_id="q_001",
    )
    for content in captured:
        assert "version" not in content.lower() or "被测版本" not in content


def test_score_question_schema_invalid_fails():
    def bad_complete(messages: list[dict[str, str]], response_model: type) -> Any:
        if response_model is ContextJudgment:
            return {"helpful": "yes"}  # wrong type
        if response_model is FaithfulnessJudgment:
            return FaithfulnessJudgment(claims_verdict=["supported"])
        return RelevanceJudgment(relevance_likert=4)

    client = StructuredEvalClient(complete=bad_complete)
    with pytest.raises(JudgeError):
        score_question(
            client=client,
            question="问题？",
            answer="答案。",
            chunks=[{"chunk_id": "c1", "text": "t"}],
            repetitions=1,
            seed=42,
            question_id="q_001",
        )


def test_score_question_real_chunk_shape():
    chunk_path = Path("data/chunks/doc_d97773f1500c.jsonl")
    if not chunk_path.exists():
        pytest.skip("真实 chunk 不存在")

    import json
    chunks = []
    for line in chunk_path.read_text(encoding="utf-8").splitlines()[:3]:
        chunks.append(json.loads(line))

    def complete(messages: list[dict[str, str]], response_model: type) -> Any:
        if response_model is ContextJudgment:
            return ContextJudgment(helpful=[True] * len(chunks))
        if response_model is FaithfulnessJudgment:
            return FaithfulnessJudgment(claims_verdict=["supported"])
        return RelevanceJudgment(relevance_likert=4)

    client = StructuredEvalClient(complete=complete)
    result = score_question(
        client=client,
        question="消防监督检查规定第十条规定了什么？",
        answer="第十条内容。",
        chunks=chunks,
        repetitions=1,
        seed=42,
        question_id="q_real_001",
    )
    assert 0 <= result.context_relevancy <= 1
    assert 0 <= result.faithfulness <= 1
    assert 0 <= result.answer_relevance <= 1
