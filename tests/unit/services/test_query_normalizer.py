from app.services.query_normalizer import normalize_query


def test_normalize_query_expands_fire_law_alias():
    normalized = normalize_query("消防法关于职责的规定")

    assert normalized.canonical_terms[0] == "中华人民共和国消防法"
    assert "职责" in normalized.intent_terms
    assert "中华人民共和国消防法" in normalized.keyword_terms


def test_normalize_query_extracts_region_article_and_effective_date():
    normalized = normalize_query("河北消防条例第28条自2010年7月1日起施行吗")

    assert normalized.region == "河北省"
    assert normalized.article_no == "第二十八条"
    assert normalized.effective_on == "2010年7月1日"
    assert "河北省消防条例" in normalized.canonical_terms
