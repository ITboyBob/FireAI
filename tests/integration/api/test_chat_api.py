from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.chat import get_chat_client, get_retriever
from app.main import create_app
from app.services.answer_service import MODEL_FAILURE_UNCERTAINTY


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, top_k: int):
        self.calls.append((query, top_k))
        return self.results


class FakeChatClient:
    def __init__(self, payload=None, *, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.payload


def test_chat_endpoint_returns_structured_answer():
    retriever = FakeRetriever(
        [
            {
                "chunk_id": "xiaofangfa_2019#article-2",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
                "text": "国家实行消防安全责任制。",
                "article_no": "第二条",
            }
        ]
    )
    chat_client = FakeChatClient(
        {
            "conclusion": "国家实行消防安全责任制。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "未检索到与问题直接冲突的其他条文。",
        }
    )
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_chat_client] = lambda: chat_client
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "消防法关于职责怎么规定？", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"conclusion", "citations", "scope", "uncertainty", "evidence"}
    assert body["conclusion"] == "国家实行消防安全责任制。"
    assert body["citations"] == ["《中华人民共和国消防法》第二条"]
    assert body["evidence"][0]["chunk_id"] == "xiaofangfa_2019#article-2"
    assert retriever.calls == [("消防法关于职责怎么规定？", 3)]
    assert len(chat_client.calls) == 1


def test_chat_endpoint_returns_refusal_when_evidence_is_empty():
    retriever = FakeRetriever([])
    chat_client = FakeChatClient(
        {
            "conclusion": "这条回答不应被使用。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "",
            "uncertainty": "",
        }
    )
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_chat_client] = lambda: chat_client
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "没有证据时怎么返回？"})

    assert response.status_code == 200
    assert response.json() == {
        "conclusion": "证据不足，无法可靠回答。",
        "citations": [],
        "scope": "",
        "uncertainty": "当前检索结果不足以支持结论。",
        "evidence": [],
    }
    assert retriever.calls == [("没有证据时怎么返回？", 5)]
    assert chat_client.calls == []


def test_chat_endpoint_returns_503_when_index_is_not_ready():
    app = create_app()

    def _raise_index_not_ready():
        raise HTTPException(status_code=503, detail="尚未完成建库")

    app.dependency_overrides[get_retriever] = _raise_index_not_ready
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "现在能查吗？"})

    assert response.status_code == 503
    assert response.json() == {"detail": "尚未完成建库"}


def test_chat_endpoint_returns_502_when_model_call_fails():
    retriever = FakeRetriever(
        [
            {
                "chunk_id": "xiaofangfa_2019#article-2",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
                "text": "国家实行消防安全责任制。",
                "article_no": "第二条",
            }
        ]
    )
    chat_client = FakeChatClient(error=RuntimeError("upstream unavailable"))
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_chat_client] = lambda: chat_client
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "消防法关于职责怎么规定？"})

    assert response.status_code == 502
    assert response.json() == {"detail": MODEL_FAILURE_UNCERTAINTY}
