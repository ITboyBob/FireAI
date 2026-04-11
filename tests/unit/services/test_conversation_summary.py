from app.services.conversation_summary import ConversationSummaryManager


def test_build_history_summary_compacts_older_turns():
    manager = ConversationSummaryManager()
    older_turns = [
        {
            "question": "消防法关于消防安全责任制怎么规定？",
            "legal_basis": ["《中华人民共和国消防法》第二条"],
            "correction_notice": "",
        },
        {
            "question": "河北也适用吗？",
            "legal_basis": ["《河北省消防条例》第二十八条"],
            "correction_notice": "本轮已根据最新检索证据修正前文。",
        },
    ]

    summary = manager.build_summary(older_turns)

    assert "中华人民共和国消防法" in summary
    assert "河北省消防条例" in summary
    assert "已修正前文" in summary
