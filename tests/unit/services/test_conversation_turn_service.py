import pytest

from app.services.context_manager import ContextManager
from app.services.conversation_presenter import ConversationPresenter
from app.services.conversation_repository import ConversationRepository
from app.services.conversation_service import ConversationService
from app.services.conversation_summary import ConversationSummaryManager
from app.services.conversation_turn_service import ConversationTurnService
from app.services.chat_client import ChatCompletionError
from app.services.turn_classifier import TurnClassifier


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, *, top_k: int):
        self.calls.append(query)
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


class FakeChatClient:
    def complete(self, messages):
        del messages
        return {
            "conclusion": "国家实行消防安全责任制。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "",
        }


class FailingChatClient:
    def complete(self, messages):
        del messages
        raise RuntimeError("upstream unavailable")


class FakeKnowledgeVersionResolver:
    def resolve(self) -> str:
        return "kb:test"


class FailingSummaryManager:
    def build_summary(self, older_turns):
        del older_turns
        raise RuntimeError("summary unavailable")


def _build_service(repo: ConversationRepository, *, summary_manager=None, summary_trigger_turns: int = 6):
    conversation_service = ConversationService(repository=repo)
    retriever = FakeRetriever()
    service = ConversationTurnService(
        repository=repo,
        conversation_service=conversation_service,
        turn_classifier=TurnClassifier(),
        context_manager=ContextManager(window_turns=1),
        summary_manager=summary_manager or ConversationSummaryManager(),
        knowledge_version_resolver=FakeKnowledgeVersionResolver(),
        retriever=retriever,
        chat_client=FakeChatClient(),
        presenter=ConversationPresenter(),
        summary_trigger_turns=summary_trigger_turns,
    )
    service.retriever = retriever
    return service


def _build_service_with_chat_client(
    repo: ConversationRepository,
    *,
    chat_client,
    summary_manager=None,
    summary_trigger_turns: int = 6,
):
    conversation_service = ConversationService(repository=repo)
    retriever = FakeRetriever()
    service = ConversationTurnService(
        repository=repo,
        conversation_service=conversation_service,
        turn_classifier=TurnClassifier(),
        context_manager=ContextManager(window_turns=1),
        summary_manager=summary_manager or ConversationSummaryManager(),
        knowledge_version_resolver=FakeKnowledgeVersionResolver(),
        retriever=retriever,
        chat_client=chat_client,
        presenter=ConversationPresenter(),
        summary_trigger_turns=summary_trigger_turns,
    )
    service.retriever = retriever
    return service


def _seed_previous_turn(repo: ConversationRepository, service: ConversationService, conversation_id: str) -> None:
    user_message = repo.append_message(conversation_id, role="user", content="消防法关于消防安全责任制怎么规定？")
    service.note_first_user_message(conversation_id, user_message.content)
    assistant_message = repo.append_message(conversation_id, role="assistant", content="国家实行消防安全责任制。")
    turn = repo.create_turn(
        conversation_id=conversation_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        is_followup=False,
        rewritten_query="中华人民共和国消防法 第二条 消防法关于消防安全责任制怎么规定？",
        history_summary_used="",
        knowledge_version="kb:seed",
        correction_notice="",
    )
    repo.save_answer_snapshot(
        turn_id=turn.id,
        answer="国家实行消防安全责任制。",
        legal_basis=["《中华人民共和国消防法》第二条"],
        clause_texts=[{"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}],
    )


def test_handle_user_message_requeries_with_context_hints(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)

    conversation = service.conversation_service.create_conversation()
    _seed_previous_turn(repo, service.conversation_service, conversation.id)

    result = service.handle_user_message(conversation.id, "它第二条怎么说？")
    detail = repo.get_conversation_detail(conversation.id)
    latest_turn = detail.turns[-1]

    assert result.assistant.legal_basis == ["《中华人民共和国消防法》第二条"]
    assert "中华人民共和国消防法" in service.retriever.calls[0].vector_query
    assert latest_turn.knowledge_version == "kb:test"
    assert "中华人民共和国消防法" in latest_turn.rewritten_query


def test_handle_user_message_sets_auto_title_and_saves_turn_metadata(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)

    conversation = service.conversation_service.create_conversation()

    service.handle_user_message(conversation.id, "消防法关于消防安全责任制怎么规定？")
    detail = repo.get_conversation_detail(conversation.id)
    latest_turn = detail.turns[-1]

    assert detail.conversation.title == "消防法关于消防安全责任制怎么规定"
    assert latest_turn.knowledge_version == "kb:test"
    assert latest_turn.history_summary_used == ""
    assert "消防法关于消防安全责任制怎么规定？" in latest_turn.rewritten_query


def test_handle_user_message_degrades_when_summary_unavailable(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(
        repo,
        summary_manager=FailingSummaryManager(),
        summary_trigger_turns=1,
    )

    conversation = service.conversation_service.create_conversation()
    _seed_previous_turn(repo, service.conversation_service, conversation.id)

    service.handle_user_message(conversation.id, "河北也适用吗？")
    detail = repo.get_conversation_detail(conversation.id)

    assert detail.turns[-1].history_summary_used == ""


def test_handle_user_message_raises_when_model_call_fails(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service_with_chat_client(repo, chat_client=FailingChatClient())

    conversation = service.conversation_service.create_conversation()

    with pytest.raises(ChatCompletionError, match="模型调用失败"):
        service.handle_user_message(conversation.id, "消防法关于消防安全责任制怎么规定？")
