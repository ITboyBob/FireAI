from __future__ import annotations

import pytest

from scripts.eval_ws_rag.eval_chat_client import (
    ContextJudgment,
    EvalClientError,
    FaithfulnessJudgment,
    RelevanceJudgment,
    StructuredEvalClient,
    _extract_json_object,
    _provider_prefers_text_json,
    build_judge_client,
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


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://ark.cn-beijing.volces.com/api/v3", True),
        ("https://api.iflow.cn/v1", True),
        ("https://api.openai.com/v1", False),
    ],
)
def test_provider_prefers_text_json(base_url, expected):
    assert _provider_prefers_text_json(base_url) is expected


@pytest.mark.parametrize(
    "content,expected",
    [
        ('{"helpful": [true, false]}', {"helpful": [True, False]}),
        ('```json\n{"claims_verdict": ["supported"]}\n```', {"claims_verdict": ["supported"]}),
        ('说明：\n{"relevance_likert": 4}\n完毕', {"relevance_likert": 4}),
    ],
)
def test_extract_json_object(content, expected):
    assert _extract_json_object(content) == expected


def test_extract_json_object_raises_when_no_json():
    with pytest.raises(ValueError):
        _extract_json_object("没有 JSON 内容")


def test_build_judge_client_falls_back_to_text_json_for_volces(monkeypatch):
    """火山方舟端点应使用 text response_format 并解析返回的 JSON 字符串。"""

    class FakeMessage:
        content = '{"helpful": [true]}'

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["response_format"]["type"] == "text"
            return FakeResponse()

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("openai.OpenAI", lambda **_: FakeClient())

    client = build_judge_client(
        api_key="fake",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="deepseek-v4-pro-260425",
        max_retries=0,
        timeout=5,
    )
    result = client.call(
        [{"role": "user", "content": "context"}], response_model=ContextJudgment
    )
    assert result.helpful == [True]
    assert client.model == "deepseek-v4-pro-260425"
