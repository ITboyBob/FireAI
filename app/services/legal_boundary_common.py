"""正文边界策略公共辅助函数。

本模块从 S1 边界策略中抽取 S1/S2/S3 复用的纯函数，保持原行为不变。
所有函数均无外部副作用，不依赖具体策略状态。
"""

from __future__ import annotations

import re
import unicodedata

from app.services.legal_extractor import ExtractedBlock
from app.services.legal_intermediate import BodyUnit, SourceSpan


ARTICLE_PATTERN = re.compile(
    r"^第([一二三四五六七八九十百千万零〇两0-9]+)条(?:\s|　|$)"
)
HEADING_PATTERN = re.compile(
    r"^第[一二三四五六七八九十百千万零〇两0-9]+([编章节])(?:\s|　|$)"
)
PAGE_FIELD_PATTERN = re.compile(r"(?:PAGE|MERGEFORMAT)")
PAGE_LINE_PATTERN = re.compile(r"^第?\s*\d+\s*页?$")
PRINT_RECORD_PATTERN = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*印发[。.]?$"
)
COPY_DISTRIBUTION_PATTERN = re.compile(r"^抄送\s*[：:]")
ADMIN_OFFICE_FOOTER_PATTERN = re.compile(
    r"^[^，,；;：:]{2,40}(?:办公室|办公厅)[。.]?$"
)
LOCAL_GOVERNMENT_REGULATION_FOOTER_PATTERN = re.compile(
    r"^(?!本(?:规定|办法|细则|条例))[一-鿿]{1,16}"
    r"(?:省|市|自治区|自治州|县)人民政府规章[。.]?$"
)


def normalize_title(value: str) -> str:
    """规范化法规标题，用于唯一标题匹配。"""
    normalized = unicodedata.normalize("NFKC", value).strip()
    return re.sub(r"[\s《》]+", "", normalized)


def chinese_number_to_int(value: str) -> int:
    """把中文数字字符串转换为整数，也兼容阿拉伯数字。"""
    if value.isdigit():
        return int(value)
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    current = 0
    for character in value:
        if character in digits:
            current = digits[character]
            continue
        unit = units[character]
        total += (current or 1) * unit
        current = 0
    return total + current


def article_number(block: ExtractedBlock) -> int:
    """从条文块文本中提取条号；不匹配时抛出 ValueError。"""
    match = ARTICLE_PATTERN.match(block.text.strip())
    if match is None:
        raise ValueError("条文块缺少条号")
    return chinese_number_to_int(match.group(1))


def body_unit(
    *,
    block: ExtractedBlock,
    unit_id: str,
    kind: str,
    text: str,
    parent_unit_id: str | None = None,
) -> BodyUnit:
    """构造一个正文单元。"""
    return BodyUnit(
        unit_id=unit_id,
        kind=kind,  # type: ignore[arg-type]
        text=text,
        source_span=SourceSpan(
            start=block.location,
            end=block.location,
            start_char_offset=0,
            end_char_offset=len(block.text),
        ),
        parent_unit_id=parent_unit_id,
    )


def build_body_units(
    blocks: tuple[ExtractedBlock, ...],
    *,
    title_index: int,
    first_article_index: int,
    body_end: int,
    expected_title: str,
) -> tuple[BodyUnit, ...]:
    """从已确认的标题、第一条和正文结束位置构建正文单元。"""
    units: list[BodyUnit] = [
        body_unit(
            block=blocks[title_index],
            unit_id="unit-0",
            kind="title",
            text=expected_title,
        )
    ]
    current_parent = "unit-0"
    current_article: str | None = None
    for index in range(title_index + 1, body_end + 1):
        block = blocks[index]
        text = block.text.strip()
        if not text:
            continue
        heading_match = HEADING_PATTERN.match(text)
        article_match = ARTICLE_PATTERN.match(text)
        if index < first_article_index and not heading_match:
            continue
        if heading_match:
            kind = {
                "编": "part",
                "章": "chapter",
                "节": "section",
            }[heading_match.group(1)]
            unit_id = f"unit-{len(units)}"
            units.append(
                body_unit(
                    block=block,
                    unit_id=unit_id,
                    kind=kind,
                    text=text,
                    parent_unit_id="unit-0",
                )
            )
            current_parent = unit_id
            continue
        if article_match:
            unit_id = f"unit-{len(units)}"
            units.append(
                body_unit(
                    block=block,
                    unit_id=unit_id,
                    kind="article",
                    text=text,
                    parent_unit_id=current_parent,
                )
            )
            current_article = unit_id
            continue
        if current_article is not None:
            units.append(
                body_unit(
                    block=block,
                    unit_id=f"unit-{len(units)}",
                    kind="paragraph",
                    text=text,
                    parent_unit_id=current_article,
                )
            )
    return tuple(units)


def is_tail_marker(text: str) -> bool:
    """判断文本是否为尾部噪声信号（页码域、页码行、印发记录）。"""
    return (
        bool(PAGE_FIELD_PATTERN.search(text))
        or bool(PAGE_LINE_PATTERN.fullmatch(text))
        or bool(PRINT_RECORD_PATTERN.search(text))
    )


def is_footer_line(text: str) -> bool:
    """判断文本是否为普通页脚或印发尾注。"""
    return (
        bool(ADMIN_OFFICE_FOOTER_PATTERN.fullmatch(text))
        or bool(LOCAL_GOVERNMENT_REGULATION_FOOTER_PATTERN.fullmatch(text))
        or bool(COPY_DISTRIBUTION_PATTERN.match(text))
    )


def find_tail_boundary(
    blocks: tuple[ExtractedBlock, ...],
    *,
    last_article_index: int,
    region_end: int | None = None,
) -> tuple[int | None, int, bool]:
    """在正文最后一个条文之后查找尾部边界。

    返回 (tail_start, body_end, tail_ambiguous)。
    若未找到尾部信号，tail_start 为 None，body_end 为 last_article_index。
    """
    if region_end is None:
        region_end = len(blocks)
    tail_start: int | None = None
    body_end = last_article_index
    blank_seen = False
    for index in range(last_article_index + 1, region_end):
        text = blocks[index].text.strip()
        if tail_start is not None:
            continue
        if not text:
            blank_seen = True
            continue
        if is_tail_marker(text) or (blank_seen and is_footer_line(text)):
            tail_start = index
            continue
        if blank_seen:
            return None, body_end, True
        body_end = index
    return tail_start, body_end, False
