from fastapi.testclient import TestClient

from app.api.chat import get_chat_client, get_retriever
from app.api.conversations import get_conversation_service, get_conversation_turn_service
from app.core.settings import Settings, get_settings
from app.main import create_app
from app.services.chat_client import ChatCompletionError


class FakeConversationService:
    def __init__(self):
        self.conversations = [
            {
                "id": "conv-1",
                "title": "新会话",
                "auto_title": True,
                "updated_at": "2026-04-11T10:00:00Z",
                "last_message_at": None,
            }
        ]

    def create_conversation(self):
        return self.conversations[0]

    def list_conversations(self):
        return self.conversations

    def get_conversation_detail(self, conversation_id: str):
        from app.services.conversation_repository import ConversationNotFoundError
        if conversation_id != "conv-1":
            raise ConversationNotFoundError(conversation_id)
        return {
            "conversation": self.conversations[0],
            "messages": [],
            "history_summary": "",
        }

    def rename_conversation(self, conversation_id: str, title: str):
        assert conversation_id == "conv-1"
        self.conversations[0]["title"] = title
        self.conversations[0]["auto_title"] = False
        return self.conversations[0]

    def delete_conversation(self, conversation_id: str):
        assert conversation_id == "conv-1"
        self.conversations.clear()


class FakeConversationTurnService:
    def handle_user_message(self, conversation_id: str, message: str):
        assert conversation_id == "conv-1"
        assert message == "消防法第二条怎么说？"
        return {
            "assistant": {
                "message_id": "msg-2",
                "answer": "国家实行消防安全责任制。",
                "legal_basis": ["《中华人民共和国消防法》第二条"],
                "clause_texts": [
                    {"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}
                ],
                "correction_notice": "",
                "created_at": "2026-04-11T10:00:00Z",
            }
        }

    def handle_user_message_stream(self, conversation_id: str, message: str):
        from app.schemas.conversation import ConversationStreamEvent
        assert conversation_id == "conv-1"
        assert message == "消防法第二条怎么说？"
        yield ConversationStreamEvent(event="received", data={"persisted": True})
        yield ConversationStreamEvent(
            event="completed",
            assistant={
                "message_id": "msg-2",
                "answer": "国家实行消防安全责任制。",
                "legal_basis": ["《中华人民共和国消防法》第二条"],
                "clause_texts": [
                    {"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}
                ],
                "correction_notice": "",
                "created_at": "2026-04-11T10:00:00Z",
            }
        )


class FailingConversationTurnService:
    def handle_user_message(self, conversation_id: str, message: str):
        assert conversation_id == "conv-1"
        assert message == "消防法第二条怎么说？"
        raise ChatCompletionError("模型调用失败：Your API Token has expired.")

    def handle_user_message_stream(self, conversation_id: str, message: str):
        from app.schemas.conversation import ConversationStreamEvent
        assert conversation_id == "conv-1"
        assert message == "消防法第二条怎么说？"
        yield ConversationStreamEvent(event="received", data={"persisted": True})
        raise ChatCompletionError("模型调用失败：Your API Token has expired.")


class RealFlowRetriever:
    def search(self, query, *, top_k: int):
        del query, top_k
        return [
            {
                "chunk_id": "xiaofangfa_2019#article-2",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
                "text": "国家实行消防安全责任制。",
                "article_no": "第二条",
            }
        ]


class RealFlowChatClient:
    def complete(self, messages):
        del messages
        return {
            "conclusion": "国家实行消防安全责任制。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "",
        }


def test_create_conversation_then_send_message_returns_assistant_payload():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FakeConversationTurnService()
    client = TestClient(app)

    created = client.post("/api/conversations", json={})
    conversation_id = created.json()["id"]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "消防法第二条怎么说？"},
    )

    assert created.status_code == 201
    assert response.status_code == 200
    assert set(response.json()["assistant"].keys()) == {
        "message_id",
        "answer",
        "legal_basis",
        "clause_texts",
        "correction_notice",
        "created_at",
    }


def test_conversation_management_endpoints_round_trip():
    service = FakeConversationService()
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: service
    client = TestClient(app)

    listed = client.get("/api/conversations")
    detail = client.get("/api/conversations/conv-1")
    renamed = client.patch("/api/conversations/conv-1", json={"title": "河北消防条例"})
    deleted = client.delete("/api/conversations/conv-1")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "conv-1"
    assert detail.status_code == 200
    assert detail.json()["conversation"]["title"] == "新会话"
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "河北消防条例"
    assert deleted.status_code == 204


def test_send_message_returns_502_when_model_call_fails():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FailingConversationTurnService()
    client = TestClient(app)

    response = client.post(
        "/api/conversations/conv-1/messages",
        json={"message": "消防法第二条怎么说？"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "模型调用失败：Your API Token has expired."}


def test_conversation_detail_returns_history_summary_from_real_turn_flow(tmp_path):
    settings = Settings.model_validate(
        {
            "conversation_db_path": tmp_path / "conversations.db",
            "conversation_context_window_turns": 1,
            "conversation_summary_trigger_turns": 2,
        }
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_retriever] = lambda: RealFlowRetriever()
    app.dependency_overrides[get_chat_client] = lambda: RealFlowChatClient()
    client = TestClient(app)

    conversation_id = client.post("/api/conversations", json={}).json()["id"]
    first = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "消防法关于消防安全责任制怎么规定？"},
    )
    second = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "它第二条怎么说？"},
    )
    detail = client.get(f"/api/conversations/{conversation_id}")

    assert second.status_code == 200
    assert detail.status_code == 200
    assert "消防法关于消防安全责任制怎么规定？" in detail.json()["history_summary"]


def test_send_message_stream_returns_ndjson():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FakeConversationTurnService()
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/conversations/conv-1/messages/stream",
        json={"message": "消防法第二条怎么说？"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson; charset=utf-8"
        lines = list(response.iter_lines())

    assert len(lines) == 2
    import json
    received = json.loads(lines[0])
    assert received["event"] == "received"
    assert received["data"]["persisted"] is True

    completed = json.loads(lines[1])
    assert completed["event"] == "completed"
    assert completed["assistant"]["answer"] == "国家实行消防安全责任制。"


def test_send_message_stream_returns_error_event_on_failure():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FailingConversationTurnService()
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/conversations/conv-1/messages/stream",
        json={"message": "消防法第二条怎么说？"},
    ) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    assert len(lines) == 2
    import json
    received = json.loads(lines[0])
    assert received["event"] == "received"

    error_event = json.loads(lines[1])
    assert error_event["event"] == "error"
    assert error_event["code"] == "model_error"


def test_send_message_stream_returns_404_if_conversation_not_found():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FakeConversationTurnService()
    client = TestClient(app)

    response = client.post(
        "/api/conversations/conv-999/messages/stream",
        json={"message": "消防法第二条怎么说？"},
    )
    assert response.status_code == 404
