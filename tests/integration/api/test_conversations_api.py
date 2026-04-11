from fastapi.testclient import TestClient

from app.api.conversations import get_conversation_service, get_conversation_turn_service
from app.main import create_app


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
        assert conversation_id == "conv-1"
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
