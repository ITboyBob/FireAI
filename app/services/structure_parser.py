from dataclasses import asdict, dataclass, replace
from pathlib import Path
import json
import re

from app.services.legal_intermediate import (
    BodyUnit,
    LegalDocumentIntermediate,
    SourceSpan,
    validate_legal_intermediate,
)


ARTICLE_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千万零〇两]+条)\s*(.*)$")
HEADING_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千万零〇两]+)([编章节])\s*(.*)$")
DATE_PATTERN = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
DATE_ONLY_PATTERN = re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日$")
NUMBERED_DECREE_PATTERN = re.compile(r"^〔\d{4}〕第\d+号$")
EFFECTIVE_DATE_PATTERN = re.compile(
    r"自\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*起施行"
)


@dataclass(frozen=True)
class ParsedArticle:
    article_no: str
    chapter_title: str | None
    heading_path: tuple[str, ...]
    text: str
    source_span: SourceSpan | None = None


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    title: str
    issuing_authority: str | None
    region: str | None
    promulgated_on: str | None
    effective_on: str | None
    articles: list[ParsedArticle]
    source_sha256: str | None = None
    extraction_class: str | None = None
    content_class: str | None = None
    boundary_status: str | None = None
    version_basis: str | None = None


def parse_legal_document(document_id: str, raw_text: str) -> ParsedDocument:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return ParsedDocument(
            document_id=document_id,
            title=document_id,
            issuing_authority=None,
            region=None,
            promulgated_on=None,
            effective_on=None,
            articles=[],
        )

    title = _extract_title(lines)
    title_index = lines.index(title)
    pre_title_lines = lines[:title_index]
    body_lines = lines[title_index + 1 :]
    first_article_offset = _find_first_article_index(body_lines)
    post_title_metadata_lines = body_lines[:first_article_offset]

    return ParsedDocument(
        document_id=document_id,
        title=title,
        issuing_authority=_extract_issuing_authority(lines[: title_index + 1]),
        region=_extract_region(title),
        promulgated_on=_extract_promulgated_on(
            pre_title_lines,
            post_title_metadata_lines,
        ),
        effective_on=_extract_effective_on(lines),
        articles=_parse_articles(body_lines),
    )


def parse_legal_intermediate(
    intermediate: LegalDocumentIntermediate,
) -> ParsedDocument:
    validate_legal_intermediate(intermediate)
    if intermediate.boundary.status != "confirmed":
        raise ValueError("只有 confirmed 中间格式可以进入结构解析")

    parsed = parse_legal_document(
        intermediate.document_id,
        intermediate.body_text,
    )
    if parsed.document_id != intermediate.document_id:
        raise ValueError("结构解析结果的 document_id 与中间格式不一致")
    if parsed.title != intermediate.target.title:
        raise ValueError("结构解析结果标题超出 confirmed 目标正文")

    article_units = tuple(
        unit for unit in intermediate.body_units if unit.kind == "article"
    )
    if len(parsed.articles) != len(article_units):
        raise ValueError("结构解析结果条文数量与 confirmed 正文不一致")

    bound_articles = [
        _bind_article_source_span(
            parsed_article,
            article_unit,
            intermediate.body_units,
        )
        for parsed_article, article_unit in zip(
            parsed.articles,
            article_units,
            strict=True,
        )
    ]
    return replace(
        parsed,
        articles=bound_articles,
        source_sha256=intermediate.source_ref.source_sha256,
        extraction_class=intermediate.extraction_class.value,
        content_class=intermediate.content_class.value,
        boundary_status=intermediate.boundary.status,
        version_basis=intermediate.target.version_basis,
    )


def write_structured_document(document: ParsedDocument, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{document.document_id}.json"
    output_path.write_text(
        json.dumps(asdict(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _bind_article_source_span(
    parsed_article: ParsedArticle,
    article_unit: BodyUnit,
    body_units: tuple[BodyUnit, ...],
) -> ParsedArticle:
    match = ARTICLE_PATTERN.match(article_unit.text)
    if match is None or match.group(1) != parsed_article.article_no:
        raise ValueError("结构解析结果条号与 confirmed 正文顺序不一致")

    paragraph_units = tuple(
        unit
        for unit in body_units
        if unit.kind == "paragraph"
        and unit.parent_unit_id == article_unit.unit_id
    )
    expected_text_parts = [match.group(2).strip()]
    expected_text_parts.extend(unit.text for unit in paragraph_units)
    expected_text = "\n".join(
        part for part in expected_text_parts if part
    ).strip()
    if parsed_article.text != expected_text:
        raise ValueError("结构解析结果包含边界外文本或遗漏 confirmed 正文")

    final_unit = paragraph_units[-1] if paragraph_units else article_unit
    source_span = SourceSpan(
        start=article_unit.source_span.start,
        end=final_unit.source_span.end,
        start_char_offset=article_unit.source_span.start_char_offset,
        end_char_offset=final_unit.source_span.end_char_offset,
    )
    return replace(parsed_article, source_span=source_span)


def _extract_title(lines: list[str]) -> str:
    first_opening_article_index = _find_first_opening_article_index(lines)
    if first_opening_article_index < len(lines):
        search_limit = first_opening_article_index
    else:
        first_heading_index = _find_first_heading_index(lines)
        search_limit = (
            first_heading_index
            if first_heading_index < len(lines)
            else _find_first_article_index(lines)
        )
    pre_article_lines = lines[:search_limit]
    candidates = [line for line in pre_article_lines if _looks_like_title(line)]
    if candidates:
        return candidates[-1]
    return lines[0]


def _extract_issuing_authority(lines: list[str]) -> str | None:
    for line in lines:
        authority = _normalize_authority(line)
        if authority is not None:
            return authority
    return None


def _extract_region(title: str) -> str | None:
    if title.startswith("中华人民共和国"):
        return "全国"

    for pattern in (r"^(.+?省)", r"^(.+?自治区)", r"^(.+?市)"):
        match = re.match(pattern, title)
        if match:
            return match.group(1)

    return None


def _extract_promulgated_on(
    pre_title_lines: list[str],
    post_title_metadata_lines: list[str],
) -> str | None:
    for line in post_title_metadata_lines:
        if "公布" in line:
            dates = DATE_PATTERN.findall(line)
            if dates:
                return _normalize_date(dates[0])

    standalone_dates = [
        line for line in pre_title_lines if DATE_ONLY_PATTERN.fullmatch(line)
    ]
    if standalone_dates:
        return _normalize_date(standalone_dates[-1])

    for line in pre_title_lines:
        if "公布" in line:
            dates = DATE_PATTERN.findall(line)
            if dates:
                return _normalize_date(dates[0])

    return None


def _extract_effective_on(lines: list[str]) -> str | None:
    for line in reversed(lines):
        match = EFFECTIVE_DATE_PATTERN.search(line)
        if match:
            return _normalize_date(match.group(1))
    return None


def _parse_articles(lines: list[str]) -> list[ParsedArticle]:
    articles: list[ParsedArticle] = []
    current_heading_by_unit: dict[str, str | None] = {"编": None, "章": None, "节": None}
    current_article_no: str | None = None
    current_article_lines: list[str] = []
    current_heading_path: tuple[str, ...] = ()
    current_chapter: str | None = None

    for line in lines:
        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            ordinal, unit, title = heading_match.groups()
            heading = f"{ordinal}{unit} {title}".strip()
            current_heading_by_unit[unit] = heading
            if unit == "编":
                current_heading_by_unit["章"] = None
                current_heading_by_unit["节"] = None
            elif unit == "章":
                current_heading_by_unit["节"] = None
            continue

        article_match = ARTICLE_PATTERN.match(line)
        if article_match:
            _flush_article(
                articles,
                current_article_no,
                current_chapter,
                current_heading_path,
                current_article_lines,
            )

            current_article_no = article_match.group(1)
            article_body = article_match.group(2).strip()
            current_article_lines = [article_body] if article_body else []
            current_heading_path = tuple(
                heading
                for heading in (
                    current_heading_by_unit["编"],
                    current_heading_by_unit["章"],
                    current_heading_by_unit["节"],
                )
                if heading is not None
            )
            current_chapter = current_heading_by_unit["章"]
            continue

        if current_article_no is not None:
            current_article_lines.append(line)

    _flush_article(
        articles,
        current_article_no,
        current_chapter,
        current_heading_path,
        current_article_lines,
    )
    return articles


def _flush_article(
    articles: list[ParsedArticle],
    article_no: str | None,
    chapter_title: str | None,
    heading_path: tuple[str, ...],
    article_lines: list[str],
) -> None:
    if article_no is None:
        return

    articles.append(
        ParsedArticle(
            article_no=article_no,
            chapter_title=chapter_title,
            heading_path=heading_path,
            text="\n".join(line for line in article_lines if line).strip(),
        )
    )


def _looks_like_title(line: str) -> bool:
    if (
        not line
        or ARTICLE_PATTERN.match(line)
        or HEADING_PATTERN.match(line)
        or DATE_ONLY_PATTERN.fullmatch(line)
        or NUMBERED_DECREE_PATTERN.fullmatch(line)
        or _normalize_authority(line) is not None
    ):
        return False

    if line.startswith("附件") or line.startswith("（") or line.startswith("省长："):
        return False

    if any(punctuation in line for punctuation in ("。", "；", "：")):
        return False

    return True


def _normalize_authority(line: str) -> str | None:
    if line.endswith("人民政府令"):
        return line.removesuffix("令")

    for suffix in (
        "人民政府",
        "国务院",
        "国务院办公厅",
        "全国人民代表大会常务委员会",
    ):
        if line.endswith(suffix):
            return line

    return None


def _find_first_article_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if ARTICLE_PATTERN.match(line):
            return index
    return len(lines)


def _find_first_heading_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if HEADING_PATTERN.match(line):
            return index
    return len(lines)


def _find_first_opening_article_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.startswith("第一条"):
            return index
    return len(lines)


def _normalize_date(date_text: str) -> str:
    return re.sub(r"\s+", "", date_text)
