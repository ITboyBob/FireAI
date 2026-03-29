from dataclasses import dataclass, field
import re


TITLE_ALIASES: tuple[tuple[str, str], ...] = (
    ("中华人民共和国消防法", "中华人民共和国消防法"),
    ("消防法", "中华人民共和国消防法"),
    ("河北省消防条例", "河北省消防条例"),
    ("河北消防条例", "河北省消防条例"),
    ("河北省消防安全责任制规定", "河北省消防安全责任制规定"),
    ("河北消防安全责任制规定", "河北省消防安全责任制规定"),
    ("河北责任制规定", "河北省消防安全责任制规定"),
    ("河北省消防安全责任制实施办法", "河北省消防安全责任制实施办法"),
    ("河北消防安全责任制实施办法", "河北省消防安全责任制实施办法"),
    ("消防安全责任制实施办法", "消防安全责任制实施办法"),
    ("机关、团体、企业、事业单位消防安全管理规定", "机关、团体、企业、事业单位消防安全管理规定"),
    ("机关团体企业事业单位消防安全管理规定", "机关、团体、企业、事业单位消防安全管理规定"),
)
REGION_ALIASES: tuple[tuple[str, str], ...] = (
    ("河北省", "河北省"),
    ("河北", "河北省"),
    ("全国", "全国"),
)
INTENT_TERMS: tuple[str, ...] = ("职责", "责任", "处罚", "罚款", "追责", "监督", "管理")

ARTICLE_PATTERN = re.compile(r"第?\s*([0-9]{1,3}|[零〇一二三四五六七八九十百千两]+)\s*条")
FULL_DATE_PATTERN = re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)")
YEAR_PATTERN = re.compile(r"(\d{4}年)")
PUNCTUATION_PATTERN = re.compile(r"[\s《》“”、，。！？；：,.!?:;（）()]+")
EFFECTIVE_HINT_PATTERN = re.compile(r"(施行|实施|生效)")
PROMULGATED_HINT_PATTERN = re.compile(r"(公布|发布|颁布|印发|修订)")


@dataclass(frozen=True)
class NormalizedQuery:
    original: str
    cleaned: str
    canonical_terms: list[str] = field(default_factory=list)
    keyword_terms: list[str] = field(default_factory=list)
    intent_terms: list[str] = field(default_factory=list)
    time_terms: list[str] = field(default_factory=list)
    region: str | None = None
    article_no: str | None = None
    promulgated_on: str | None = None
    effective_on: str | None = None
    vector_query: str = ""


def normalize_query(query: str) -> NormalizedQuery:
    cleaned = re.sub(r"\s+", " ", query).strip()
    canonical_terms = _extract_canonical_terms(cleaned)
    intent_terms = [term for term in INTENT_TERMS if term in cleaned]
    article_no = _extract_article_no(cleaned)
    region = _extract_region(cleaned)
    promulgated_on, effective_on, time_terms = _extract_dates(cleaned)
    keyword_terms = _unique_terms(
        [
            cleaned,
            *canonical_terms,
            article_no,
            *time_terms,
        ]
    )
    vector_query = " ".join(_unique_terms([cleaned, *canonical_terms, *intent_terms]))

    return NormalizedQuery(
        original=query,
        cleaned=cleaned,
        canonical_terms=canonical_terms,
        keyword_terms=keyword_terms,
        intent_terms=intent_terms,
        time_terms=time_terms,
        region=region,
        article_no=article_no,
        promulgated_on=promulgated_on,
        effective_on=effective_on,
        vector_query=vector_query,
    )


def _extract_canonical_terms(query: str) -> list[str]:
    simplified_query = _simplify_text(query)
    matches: list[str] = []
    for alias, canonical in TITLE_ALIASES:
        if _simplify_text(alias) in simplified_query:
            matches.append(canonical)
    return _unique_terms(matches)


def _extract_region(query: str) -> str | None:
    for alias, region in REGION_ALIASES:
        if alias in query:
            return region
    return None


def _extract_dates(query: str) -> tuple[str | None, str | None, list[str]]:
    full_dates = FULL_DATE_PATTERN.findall(query)
    years = YEAR_PATTERN.findall(query)
    promulgated_on = full_dates[0] if full_dates and PROMULGATED_HINT_PATTERN.search(query) else None
    effective_on = full_dates[0] if full_dates and EFFECTIVE_HINT_PATTERN.search(query) else None
    time_terms = _unique_terms([*full_dates, *years])
    return promulgated_on, effective_on, time_terms


def _extract_article_no(query: str) -> str | None:
    match = ARTICLE_PATTERN.search(query)
    if match is None:
        return None

    raw_value = match.group(1)
    if raw_value.isdigit():
        return f"第{_int_to_chinese(int(raw_value))}条"
    return f"第{raw_value.replace('两', '二')}条"


def _int_to_chinese(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value <= 0:
        raise ValueError("article number must be positive")
    if value < 10:
        return digits[value]
    if value < 100:
        tens, ones = divmod(value, 10)
        prefix = "十" if tens == 1 else f"{digits[tens]}十"
        return prefix if ones == 0 else f"{prefix}{digits[ones]}"

    hundreds, remainder = divmod(value, 100)
    prefix = f"{digits[hundreds]}百"
    if remainder == 0:
        return prefix
    if remainder < 10:
        return f"{prefix}零{digits[remainder]}"
    return f"{prefix}{_int_to_chinese(remainder)}"


def _simplify_text(value: str) -> str:
    return PUNCTUATION_PATTERN.sub("", value)


def _unique_terms(values: list[str | None]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        term = value.strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms
