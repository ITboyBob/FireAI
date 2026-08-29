from pathlib import Path
import sqlite3

import pytest

from app.services.conversation_repository import (
    ConversationNotFoundError,
    ConversationRepository,
    PersistenceError,
    to_persistence_error,
)


def test_repository_round_trips_conversation_and_snapshot(tmp_path: Path):
    repo = ConversationRepository(tmp_path / "conversations.db")

    conversation = repo.create_conversation(title="新会话", auto_title=True)
    user_message = repo.append_message(conversation.id, role="user", content="消防法第二条是什么？")
    assistant_message = repo.append_message(conversation.id, role="assistant", content="国家实行消防安全责任制。")
    turn = repo.create_turn(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        is_followup=False,
        rewritten_query="消防法 第二条 消防法第二条是什么？",
        history_summary_used="更早历史摘要",
        knowledge_version="kb:test",
        correction_notice="",
    )
    repo.save_answer_snapshot(
        turn_id=turn.id,
        answer="国家实行消防安全责任制。",
        legal_basis=["《中华人民共和国消防法》第二条"],
        clause_texts=[{"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}],
    )
    repo.save_history_summary(conversation.id, "更早历史摘要")

    detail = repo.get_conversation_detail(conversation.id)

    assert detail.conversation.id == conversation.id
    assert detail.messages[0].content == "消防法第二条是什么？"
    assert detail.snapshots[0].legal_basis == ["《中华人民共和国消防法》第二条"]
    assert detail.history_summary == "更早历史摘要"


def test_repository_blocks_snapshot_write_after_soft_delete(tmp_path: Path):
    repo = ConversationRepository(tmp_path / "conversations.db")

    conversation = repo.create_conversation(title="新会话", auto_title=True)
    user_message = repo.append_message(conversation.id, role="user", content="消防法第二条是什么？")
    assistant_message = repo.append_message(conversation.id, role="assistant", content="国家实行消防安全责任制。")
    turn = repo.create_turn(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        is_followup=False,
        rewritten_query="消防法 第二条 消防法第二条是什么？",
        history_summary_used="",
        knowledge_version="kb:test",
        correction_notice="",
    )

    repo.soft_delete_conversation(conversation.id)

    with pytest.raises(ConversationNotFoundError):
        repo.save_answer_snapshot(
            turn_id=turn.id,
            answer="国家实行消防安全责任制。",
            legal_basis=["《中华人民共和国消防法》第二条"],
            clause_texts=[{"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}],
        )


def test_repository_rejects_turns_that_reference_messages_from_other_conversations(tmp_path: Path):
    repo = ConversationRepository(tmp_path / "conversations.db")

    source = repo.create_conversation(title="源会话", auto_title=True)
    target = repo.create_conversation(title="目标会话", auto_title=True)
    foreign_user = repo.append_message(source.id, role="user", content="源问题")
    foreign_assistant = repo.append_message(source.id, role="assistant", content="源回答")

    with pytest.raises(ValueError, match="same conversation"):
        repo.create_turn(
            conversation_id=target.id,
            user_message_id=foreign_user.id,
            assistant_message_id=foreign_assistant.id,
            is_followup=False,
            rewritten_query="目标问题",
            history_summary_used="",
            knowledge_version="kb:test",
            correction_notice="",
        )


def test_to_persistence_error_marks_locked_operational_error_as_transient():
    converted = to_persistence_error(sqlite3.OperationalError("database is locked"))

    assert isinstance(converted, PersistenceError)
    assert converted.transient is True


def test_to_persistence_error_marks_other_sqlite_errors_as_permanent():
    converted = to_persistence_error(sqlite3.IntegrityError("FOREIGN KEY constraint failed"))

    assert isinstance(converted, PersistenceError)
    assert converted.transient is False


def test_to_persistence_error_marks_runtime_error_as_permanent():
    converted = to_persistence_error(RuntimeError("snapshot was not persisted for the created turn"))

    assert isinstance(converted, PersistenceError)
    assert converted.transient is False


def test_to_persistence_error_passes_through_unrelated_exceptions():
    value_error = ValueError("unrelated failure")
    not_found_error = ConversationNotFoundError("conv-1")

    assert to_persistence_error(value_error) is value_error
    assert to_persistence_error(not_found_error) is not_found_error
