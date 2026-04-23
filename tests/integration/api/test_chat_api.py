from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.chat import get_chat_client, get_retriever
from app.core.settings import Settings, get_settings
from app.main import create_app
from app.services.answer_service import MODEL_FAILURE_UNCERTAINTY
from app.services.chat_client import ChatCompletionError
from app.services.embedder import MissingEmbeddingDependencyError
from app.services.vector_index import VECTOR_MAP_FILENAME
from app.services.vector_store import FAISS_INDEX_FILENAME, MissingVectorStoreDependencyError


APP_JS = Path(__file__).resolve().parents[3] / "app/static/app.js"


def _build_settings_with_ready_index(tmp_path: Path) -> Settings:
    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "retrieval.db").touch()
    (index_dir / FAISS_INDEX_FILENAME).touch()
    (index_dir / VECTOR_MAP_FILENAME).write_text("[]", encoding="utf-8")
    return Settings.model_validate(
        {
            "index_dir": index_dir,
            "embedding_model_name": "test-embedding-model",
        }
    )


def test_root_page_renders_conversation_shell():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert '/static/app.css?v=' in response.text
    assert '/static/app.js?v=' in response.text
    assert 'id="home-view"' in response.text
    assert 'id="thread-view"' in response.text
    assert 'id="conversation-list"' in response.text
    assert 'id="home-composer-form"' in response.text
    assert 'id="thread-composer-form"' in response.text
    assert 'data-prompt="消防法关于消防安全责任制怎么规定？"' in response.text
    assert "本机会话模式" not in response.text
    assert "消防问答终端" not in response.text
    assert "证据优先 / 单机会话" not in response.text
    assert "系统正常" not in response.text
    assert '<p class="topbar-kicker">消防问答系统 2.0</p>' not in response.text


def test_new_conversation_button_returns_home_without_creating_empty_conversation():
    script = APP_JS.read_text(encoding="utf-8")
    listener_start = script.index('elements.newConversationButton?.addEventListener("click"')
    listener_body = script[listener_start: script.index("for (const trigger", listener_start)]

    assert "function goHome()" in script
    assert "goHome();" in listener_body
    assert "createConversation" not in listener_body


def test_conversation_page_route_renders_same_shell_with_initial_conversation_id():
    client = TestClient(create_app())

    response = client.get("/conversations/conv-123")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'data-initial-conversation-id="conv-123"' in response.text
    assert 'id="home-view"' in response.text
    assert 'id="thread-view"' in response.text
    assert 'class="thread-actions"' not in response.text
    assert 'id="rename-conversation-button"' not in response.text
    assert 'id="delete-conversation-button"' not in response.text


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


@pytest.mark.parametrize(
    ("error_factory", "expected_detail"),
    [
        (
            lambda: MissingEmbeddingDependencyError(
                "缺少 `sentence-transformers` 依赖。请先在 `fire` 环境安装它，再运行真实本地嵌入。"
            ),
            "缺少 `sentence-transformers` 依赖。请先在 `fire` 环境安装它，再运行真实本地嵌入。",
        ),
        (
            lambda: MissingVectorStoreDependencyError(
                "缺少 `faiss-cpu` 依赖。请先在 `fire` 环境安装 `numpy` 和 `faiss-cpu`。"
            ),
            "缺少 `faiss-cpu` 依赖。请先在 `fire` 环境安装 `numpy` 和 `faiss-cpu`。",
        ),
        (
            lambda: OSError("hf download failed"),
            "检索器初始化失败：hf download failed",
        ),
    ],
)
def test_chat_endpoint_returns_503_when_retriever_initialization_dependencies_are_unavailable(
    tmp_path,
    monkeypatch,
    error_factory,
    expected_detail,
):
    settings = _build_settings_with_ready_index(tmp_path)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    def _raise_dependency_error(**kwargs):
        del kwargs
        raise error_factory()

    monkeypatch.setattr(chat_api, "_build_retriever", _raise_dependency_error)
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "现在能查吗？"})

    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}


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


def test_chat_endpoint_returns_provider_detail_when_chat_client_reports_it():
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
    chat_client = FakeChatClient(error=ChatCompletionError("Your API Token has expired."))
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_chat_client] = lambda: chat_client
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "消防法关于职责怎么规定？"})

    assert response.status_code == 502
    assert response.json() == {"detail": "模型调用失败：Your API Token has expired."}
