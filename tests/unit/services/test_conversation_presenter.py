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
        "evidence": [
            {
                "title": "河北省消防条例",
                "article_no": "第二十八条",
                "path": "新路径",
                "text": "新条文原文",
            }
        ],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert payload.legal_basis == ["《河北省消防条例》第二十八条"]
    assert [item.model_dump(mode="json") for item in payload.clause_texts] == [
        {"path": "新路径", "text": "新条文原文"}
    ]
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
        "evidence": [
            {
                "title": "中华人民共和国消防法",
                "article_no": "第二条",
                "path": "新路径",
                "text": "新条文原文",
            }
        ],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert [item.model_dump(mode="json") for item in payload.clause_texts] == [
        {"path": "旧路径", "text": "旧条文原文"}
    ]
    assert payload.correction_notice == ""


def test_presenter_only_keeps_clause_texts_that_match_current_legal_basis():
    presenter = ConversationPresenter()
    current_answer = {
        "conclusion": "根据《中华人民共和国消防法》第十六条，单位的主要负责人是本单位的消防安全责任人。",
        "citations": ["《中华人民共和国消防法》第十六条"],
        "evidence": [
            {
                "title": "中华人民共和国消防法",
                "article_no": "第七十四条",
                "path": "中华人民共和国消防法 > 第七章 附则 > 第七十四条",
                "text": "本法自2009年5月1日起施行。",
            },
            {
                "title": "中华人民共和国消防法",
                "article_no": "第十六条",
                "path": "中华人民共和国消防法 > 第二章 火灾预防 > 第十六条",
                "text": "单位的主要负责人是本单位的消防安全责任人。",
            },
        ],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=None,
        is_followup=False,
    )

    assert payload.legal_basis == ["《中华人民共和国消防法》第十六条"]
    assert [item.model_dump(mode="json") for item in payload.clause_texts] == [
        {
            "path": "中华人民共和国消防法 > 第二章 火灾预防 > 第十六条",
            "text": "单位的主要负责人是本单位的消防安全责任人。",
        }
    ]


def test_presenter_does_not_mark_refusal_as_correction_notice():
    presenter = ConversationPresenter()
    previous_snapshot = {
        "legal_basis": ["《中华人民共和国消防法》第二条"],
        "clause_texts": [{"path": "旧路径", "text": "旧条文原文"}],
    }
    current_answer = {
        "conclusion": "证据不足，无法可靠回答。",
        "citations": [],
        "evidence": [],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert payload.legal_basis == []
    assert [item.model_dump(mode="json") for item in payload.clause_texts] == []
    assert payload.correction_notice == ""
