from __future__ import annotations

import pytest

from scripts.eval_ws_rag.eval_chat_client import (
    ContextJudgment,
    EvalClientError,
    FaithfulnessJudgment,
    RelevanceJudgment,
    StructuredEvalClient,
)


def test_client_returns_parsed_context_judgment():
    def complete(messages, response_model):
        return {"helpful": [True, False]}

    client = StructuredEvalClient(complete=complete)
    result = client.call(
        [{"role": "user", "content": "context"}], response_model=ContextJudgment
    )
    assert isinstance(result, ContextJudgment)
    assert result.helpful == [True, False]


def test_client_returns_parsed_faithfulness_judgment():
    def complete(messages, response_model):
        return {"claims_verdict": ["supported", "not_supported", "unknown"]}

    client = StructuredEvalClient(complete=complete)
    result = client.call(
        [{"role": "user", "content": "claims"}], response_model=FaithfulnessJudgment
    )
    assert result.claims_verdict == ["supported", "not_supported", "unknown"]


def test_client_returns_parsed_relevance_judgment():
    def complete(messages, response_model):
        return {"relevance_likert": 4}

    client = StructuredEvalClient(complete=complete)
    result = client.call(
        [{"role": "user", "content": "relevance"}], response_model=RelevanceJudgment
    )
    assert result.relevance_likert == 4


def test_client_validates_response_schema():
    def bad_complete(messages, response_model):
        # FaithfulnessJudgment expects claims_verdict, not helpful.
        return {"helpful": [True, False]}

    client = StructuredEvalClient(complete=bad_complete)
    with pytest.raises(EvalClientError):
        client.call(
            [{"role": "user", "content": "claims"}], response_model=FaithfulnessJudgment
        )


def test_client_rejects_out_of_range_likert():
    def bad_complete(messages, response_model):
        return {"relevance_likert": 6}

    client = StructuredEvalClient(complete=bad_complete)
    with pytest.raises(EvalClientError):
        client.call(
            [{"role": "user", "content": "relevance"}], response_model=RelevanceJudgment
        )


def test_client_retries_once_on_transient_error():
    calls: list[int] = []

    def flaky_complete(messages, response_model):
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("temporary")
        return {"helpful": [True]}

    client = StructuredEvalClient(complete=flaky_complete, max_retries=1)
    result = client.call(
        [{"role": "user", "content": "context"}], response_model=ContextJudgment
    )
    assert result.helpful == [True]
    assert len(calls) == 2


def test_client_raises_on_persistent_error():
    def failing_complete(messages, response_model):
        raise RuntimeError("persistent")

    client = StructuredEvalClient(complete=failing_complete, max_retries=1)
    with pytest.raises(EvalClientError):
        client.call(
            [{"role": "user", "content": "context"}], response_model=ContextJudgment
        )


def test_client_does_not_use_model_answer_schema():
    from app.schemas.chat import ModelAnswer

    def complete(messages, response_model):
        assert response_model is not ModelAnswer
        return {"helpful": [True]}

    client = StructuredEvalClient(complete=complete)
    client.call(
        [{"role": "user", "content": "context"}], response_model=ContextJudgment
    )
