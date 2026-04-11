from pathlib import Path

from app.services.conversation_repository import ConversationRepository


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
        history_summary_used="",
        knowledge_version="kb:test",
        correction_notice="",
    )
    repo.save_answer_snapshot(
        turn_id=turn.id,
        answer="国家实行消防安全责任制。",
        legal_basis=["《中华人民共和国消防法》第二条"],
        clause_texts=[{"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}],
    )

    detail = repo.get_conversation_detail(conversation.id)

    assert detail.conversation.id == conversation.id
    assert detail.messages[0].content == "消防法第二条是什么？"
    assert detail.snapshots[0].legal_basis == ["《中华人民共和国消防法》第二条"]
