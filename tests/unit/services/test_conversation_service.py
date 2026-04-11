import pytest

from app.services.conversation_repository import ConversationNotFoundError, ConversationRepository
from app.services.conversation_service import ConversationService


def test_note_first_user_message_sets_auto_title(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = ConversationService(repository=repo)

    conversation = service.create_conversation()
    service.note_first_user_message(conversation.id, "消防法关于消防安全责任制怎么规定？")

    detail = service.get_conversation_detail(conversation.id)
    assert detail.conversation.title == "消防法关于消防安全责任制怎么规定"


def test_list_conversations_orders_by_last_message_at_desc(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = ConversationService(repository=repo)

    older = service.create_conversation()
    newer = service.create_conversation()

    service.note_first_user_message(older.id, "第一个会话")
    service.note_first_user_message(newer.id, "第二个会话")

    conversations = service.list_conversations()

    assert [conversation.id for conversation in conversations] == [newer.id, older.id]


def test_service_can_rename_and_soft_delete_conversation(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = ConversationService(repository=repo)

    conversation = service.create_conversation()
    renamed = service.rename_conversation(conversation.id, "河北消防条例")
    service.delete_conversation(conversation.id)

    assert renamed.title == "河北消防条例"
    assert service.list_conversations() == []

    with pytest.raises(ConversationNotFoundError):
        service.note_first_user_message(conversation.id, "删除后不应继续写入")
