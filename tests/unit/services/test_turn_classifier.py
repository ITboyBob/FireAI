from app.services.turn_classifier import TurnClassifier


def test_classify_followup_detects_pronoun_and_inherits_title():
    classifier = TurnClassifier()
    previous_turns = [
        {
            "question": "消防法关于消防安全责任制怎么规定？",
            "legal_basis": ["《中华人民共和国消防法》第二条"],
            "canonical_title": "中华人民共和国消防法",
            "article_no": "第二条",
        }
    ]

    result = classifier.classify("它第二条怎么说？", previous_turns=previous_turns)

    assert result.is_followup is True
    assert result.context_hints["canonical_title"] == "中华人民共和国消防法"
    assert result.context_hints["article_no"] == "第二条"


def test_classify_scope_extension_followup_keeps_previous_title_without_forcing_previous_article():
    classifier = TurnClassifier()
    previous_turns = [
        {
            "question": "它第二条怎么说？",
            "legal_basis": ["《中华人民共和国消防法》第二条"],
            "canonical_title": "中华人民共和国消防法",
            "article_no": "第二条",
        }
    ]

    result = classifier.classify("河北也适用吗？", previous_turns=previous_turns)

    assert result.is_followup is True
    assert result.context_hints == {"canonical_title": "中华人民共和国消防法"}
