from app.services.conversation_repository import ConversationRepository


class ConversationService:
    def __init__(self, *, repository: ConversationRepository):
        self.repository = repository

    def create_conversation(self):
        return self.repository.create_conversation(title="新会话", auto_title=True)

    def list_conversations(self):
        return self.repository.list_conversations()

    def get_conversation_detail(self, conversation_id: str):
        return self.repository.get_conversation_detail(conversation_id)

    def rename_conversation(self, conversation_id: str, title: str):
        return self.repository.update_conversation_title(
            conversation_id,
            title=title.strip() or "新会话",
            auto_title=False,
        )

    def delete_conversation(self, conversation_id: str) -> None:
        self.repository.soft_delete_conversation(conversation_id)

    def note_first_user_message(self, conversation_id: str, message: str) -> None:
        conversation = self.repository.get_conversation(conversation_id)
        if not conversation.auto_title:
            return

        title = message.strip().rstrip("？?。.!！")[:20] or "新会话"
        self.repository.update_conversation_title(conversation_id, title=title, auto_title=False)
