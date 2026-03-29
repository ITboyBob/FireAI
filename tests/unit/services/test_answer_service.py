import json
from types import SimpleNamespace

import pytest

from app.services.answer_service import build_answer
from app.services.chat_client import ChatCompletionError, OpenAIChatClient


class FakeChatClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages):
        self.calls.append(messages)
        return self.payload


def test_build_answer_returns_refusal_when_evidence_is_empty():
    client = FakeChatClient(
        {
            "conclusion": "可以查询到相关依据。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "未检索到地方性补充规定。",
        }
    )

    result = build_answer([], client=client)

    assert result["conclusion"] == "证据不足，无法可靠回答。"
    assert result["citations"] == []
    assert result["uncertainty"] == "当前检索结果不足以支持结论。"
    assert client.calls == []


def test_build_answer_returns_structured_answer_when_citations_are_grounded():
    evidence = [
        {
            "chunk_id": "xiaofangfa_2019#article-2",
            "document_id": "xiaofangfa_2019",
            "title": "中华人民共和国消防法",
            "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
        }
    ]
    client = FakeChatClient(
        {
            "conclusion": "国家实行消防安全责任制。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "未检索到与问题直接冲突的其他条文。",
        }
    )

    result = build_answer(
        evidence,
        question="消防法关于职责怎么规定？",
        client=client,
    )

    assert result["conclusion"] == "国家实行消防安全责任制。"
    assert result["citations"] == ["《中华人民共和国消防法》第二条"]
    assert result["evidence"][0]["chunk_id"] == "xiaofangfa_2019#article-2"
    assert len(client.calls) == 1
    assert client.calls[0][0]["role"] == "system"
    assert "《中华人民共和国消防法》第二条" in client.calls[0][1]["content"]


def test_build_answer_refuses_when_citation_is_not_in_evidence():
    evidence = [
        {
            "chunk_id": "xiaofangfa_2019#article-2",
            "document_id": "xiaofangfa_2019",
            "title": "中华人民共和国消防法",
            "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
        }
    ]
    client = FakeChatClient(
        {
            "conclusion": "河北省另有补充职责规定。",
            "citations": ["《河北省消防条例》第二条"],
            "scope": "适用于河北省。",
            "uncertainty": "未说明证据缺口。",
        }
    )

    result = build_answer(evidence, question="河北还有补充规定吗？", client=client)

    assert result["conclusion"] == "证据不足，无法可靠回答。"
    assert result["citations"] == []
    assert result["uncertainty"] == "模型返回的引文无法在当前证据中验证。"


def test_openai_chat_client_uses_json_schema_response_format():
    class FakeCompletions:
        def __init__(self):
            self.last_kwargs = None

        def create(self, **kwargs):
            self.last_kwargs = kwargs
            message = SimpleNamespace(
                content=json.dumps(
                    {
                        "conclusion": "国家实行消防安全责任制。",
                        "citations": ["《中华人民共和国消防法》第二条"],
                        "scope": "适用于一般消防安全责任制说明。",
                        "uncertainty": "未检索到地方性补充规定。",
                    },
                    ensure_ascii=False,
                ),
                refusal=None,
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeSdkClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    captured: dict[str, object] = {}

    def fake_factory(**kwargs):
        client = FakeSdkClient(**kwargs)
        captured["client"] = client
        return client

    client = OpenAIChatClient(
        api_key="test-key",
        base_url="http://localhost:11434/v1",
        model="openai-compatible-model",
        timeout=12.5,
        temperature=0.0,
        client_factory=fake_factory,
    )

    result = client.complete(
        [
            {"role": "system", "content": "请严格输出 JSON。"},
            {"role": "user", "content": "问题：消防法关于职责怎么规定？"},
        ]
    )

    sdk_client = captured["client"]
    request = sdk_client.chat.completions.last_kwargs
    assert sdk_client.kwargs["api_key"] == "test-key"
    assert sdk_client.kwargs["base_url"] == "http://localhost:11434/v1"
    assert request["model"] == "openai-compatible-model"
    assert request["temperature"] == 0.0
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert result["citations"] == ["《中华人民共和国消防法》第二条"]


def test_openai_chat_client_raises_when_model_output_is_not_valid_json():
    class FakeCompletions:
        def create(self, **kwargs):
            del kwargs
            message = SimpleNamespace(content="not-json", refusal=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeSdkClient:
        def __init__(self, **kwargs):
            del kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    client = OpenAIChatClient(
        api_key="test-key",
        base_url="http://localhost:11434/v1",
        model="openai-compatible-model",
        client_factory=lambda **kwargs: FakeSdkClient(**kwargs),
    )

    with pytest.raises(ChatCompletionError, match="JSON"):
        client.complete([{"role": "system", "content": "请严格输出 JSON。"}])
