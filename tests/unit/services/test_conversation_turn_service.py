from dataclasses import replace
import sqlite3

import pytest

from app.services.context_manager import ContextManager
from app.services.conversation_presenter import ConversationPresenter
from app.services.conversation_repository import ConversationRepository, PersistenceError
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


def test_handle_user_message_scope_extension_keeps_prior_title_context(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)

    conversation = service.conversation_service.create_conversation()
    _seed_previous_turn(repo, service.conversation_service, conversation.id)

    service.handle_user_message(conversation.id, "河北也适用吗？")
    rewritten_query = service.retriever.calls[0].rewritten_query

    assert "中华人民共和国消防法" in rewritten_query
    assert "河北也适用吗？" in rewritten_query


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


def test_handle_user_message_persists_current_history_summary_for_detail_reads(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo, summary_trigger_turns=2)

    conversation = service.conversation_service.create_conversation()
    _seed_previous_turn(repo, service.conversation_service, conversation.id)

    service.handle_user_message(conversation.id, "它第二条怎么说？")
    detail = repo.get_conversation_detail(conversation.id)

    assert "消防法关于消防安全责任制怎么规定？" in detail.history_summary
    assert "《中华人民共和国消防法》第二条" in detail.history_summary


def test_handle_user_message_feeds_history_summary_into_live_retrieval(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo, summary_trigger_turns=2)

    conversation = service.conversation_service.create_conversation()
    _seed_previous_turn(repo, service.conversation_service, conversation.id)
    service.handle_user_message(conversation.id, "它第二条怎么说？")
    service.retriever.calls.clear()

    service.handle_user_message(conversation.id, "继续说明重点")

    latest_query = service.retriever.calls[0]
    assert "消防法关于消防安全责任制怎么规定？" in latest_query.vector_query
    assert "《中华人民共和国消防法》第二条" in latest_query.rewritten_query


def test_handle_user_message_raises_when_model_call_fails(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service_with_chat_client(repo, chat_client=FailingChatClient())

    conversation = service.conversation_service.create_conversation()

    with pytest.raises(ChatCompletionError, match="模型调用失败"):
        service.handle_user_message(conversation.id, "消防法关于消防安全责任制怎么规定？")


def test_handle_user_message_stream_yields_expected_event_sequence(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)

    conversation = service.conversation_service.create_conversation()

    events = list(service.handle_user_message_stream(conversation.id, "消防法关于消防安全责任制怎么规定？"))
    event_names = [e.event for e in events]

    assert event_names == ["received", "retrieving", "generating", "organizing_evidence", "completed"]

    received = events[0]
    assert received.data == {"persisted": True}

    completed = events[-1]
    assert completed.assistant is not None
    assert completed.assistant.answer == "国家实行消防安全责任制。"

    # Verify that the one-shot method still works via the stream implementation
    response = service.handle_user_message(conversation.id, "它第二条怎么说？")
    assert response.assistant.answer == "国家实行消防安全责任制。"


def test_handle_user_message_stream_wraps_locked_create_turn_as_transient_persistence_error(tmp_path, monkeypatch):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)
    conversation = service.conversation_service.create_conversation()

    def _raise_locked(*args, **kwargs):
        del args, kwargs
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo, "create_turn", _raise_locked)

    events = []
    with pytest.raises(PersistenceError) as exc_info:
        for event in service.handle_user_message_stream(conversation.id, "消防法关于消防安全责任制怎么规定？"):
            events.append(event)

    # create_turn 位于 organizing_evidence 事件之后：锁定「received 已发出后」的失败才被分型包装。
    assert [event.type for event in events] == [
        "received",
        "retrieving",
        "generating",
        "organizing_evidence",
    ]
    assert exc_info.value.transient is True


def test_handle_user_message_stream_wraps_snapshot_guard_as_permanent_persistence_error(tmp_path, monkeypatch):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)
    conversation = service.conversation_service.create_conversation()

    real_save_answer_snapshot = repo.save_answer_snapshot

    def _save_mismatched_snapshot(*args, **kwargs):
        snapshot = real_save_answer_snapshot(*args, **kwargs)
        return replace(snapshot, turn_id="turn-mismatch")

    monkeypatch.setattr(repo, "save_answer_snapshot", _save_mismatched_snapshot)

    events = []
    with pytest.raises(PersistenceError) as exc_info:
        for event in service.handle_user_message_stream(conversation.id, "消防法关于消防安全责任制怎么规定？"):
            events.append(event)

    assert [event.type for event in events] == [
        "received",
        "retrieving",
        "generating",
        "organizing_evidence",
    ]
    assert exc_info.value.transient is False


def test_handle_user_message_stream_propagates_pre_received_sqlite_error_unchanged(tmp_path, monkeypatch):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = _build_service(repo)
    conversation = service.conversation_service.create_conversation()

    def _raise_sqlite_error(*args, **kwargs):
        del args, kwargs
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(repo, "append_message", _raise_sqlite_error)

    events = []
    with pytest.raises(sqlite3.OperationalError, match="disk I/O error") as exc_info:
        for event in service.handle_user_message_stream(conversation.id, "消防法关于消防安全责任制怎么规定？"):
            events.append(event)

    assert events == []
    assert not isinstance(exc_info.value, PersistenceError)
