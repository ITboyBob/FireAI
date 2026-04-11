from app.services.conversation_presenter import ConversationPresenter


def test_presenter_switches_to_new_clause_text_when_basis_changes():
    presenter = ConversationPresenter()
    previous_snapshot = {
        "legal_basis": ["《中华人民共和国消防法》第二条"],
        "clause_texts": [{"path": "旧路径", "text": "旧条文原文"}],
    }
    current_answer = {
        "conclusion": "河北省另有补充规定。",
        "citations": ["《河北省消防条例》第二十八条"],
        "evidence": [{"path": "新路径", "text": "新条文原文"}],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert payload.legal_basis == ["《河北省消防条例》第二十八条"]
    assert payload.clause_texts == [{"path": "新路径", "text": "新条文原文"}]
    assert payload.correction_notice == "本轮已根据最新检索证据修正前文。"


def test_presenter_reuses_previous_clause_text_when_basis_unchanged():
    presenter = ConversationPresenter()
    previous_snapshot = {
        "legal_basis": ["《中华人民共和国消防法》第二条"],
        "clause_texts": [{"path": "旧路径", "text": "旧条文原文"}],
    }
    current_answer = {
        "conclusion": "国家实行消防安全责任制。",
        "citations": ["《中华人民共和国消防法》第二条"],
        "evidence": [{"path": "新路径", "text": "新条文原文"}],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert payload.clause_texts == [{"path": "旧路径", "text": "旧条文原文"}]
    assert payload.correction_notice == ""
