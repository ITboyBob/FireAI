from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal

from app.services.legal_extractor import SourceLocation
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    SourceRef,
)


BoundaryStatus = Literal["confirmed", "review_required", "rejected"]
BodyUnitKind = Literal[
    "title",
    "part",
    "chapter",
    "section",
    "article",
    "paragraph",
]
ALLOWED_BODY_UNIT_KINDS = frozenset(
    {"title", "part", "chapter", "section", "article", "paragraph"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSpan:
    start: SourceLocation
    end: SourceLocation
    start_char_offset: int
    end_char_offset: int

    def __post_init__(self) -> None:
        if self.start_char_offset < 0 or self.end_char_offset < 0:
            raise ValueError("来源字符偏移不能为负数")
        if _position_key(self.start, self.start_char_offset) > _position_key(
            self.end,
            self.end_char_offset,
        ):
            raise ValueError("来源范围起点不能晚于终点")


@dataclass(frozen=True, slots=True, kw_only=True)
class BodyUnit:
    unit_id: str
    kind: BodyUnitKind
    text: str
    source_span: SourceSpan
    parent_unit_id: str | None = None

    def __post_init__(self) -> None:
        if not self.unit_id or self.kind not in ALLOWED_BODY_UNIT_KINDS:
            raise ValueError("正文单元必须包含稳定 id 和允许的类型")
        if not self.text:
            raise ValueError("正文单元文本不能为空")


@dataclass(frozen=True, slots=True, kw_only=True)
class TargetMetadata:
    title: str
    issuing_authority: str | None = None
    region: str | None = None
    promulgated_on: str | None = None
    effective_on: str | None = None
    revision_events: tuple[str, ...] = field(default_factory=tuple)
    version_basis: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("目标法规标题不能为空")


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundaryDecision:
    status: BoundaryStatus
    start: SourceLocation | None
    end: SourceLocation | None
    title_evidence: tuple[str, ...] = field(default_factory=tuple)
    start_evidence: tuple[str, ...] = field(default_factory=tuple)
    end_evidence: tuple[str, ...] = field(default_factory=tuple)
    ambiguities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in {"confirmed", "review_required", "rejected"}:
            raise ValueError("未知正文边界状态")
        if self.status == "confirmed" and (self.start is None or self.end is None):
            raise ValueError("confirmed 边界必须包含起点和终点")
        if self.status != "confirmed" and not self.ambiguities:
            raise ValueError("非 confirmed 边界必须记录阻断原因")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExcludedRange:
    source_span: SourceSpan
    kind: str
    reason: str

    def __post_init__(self) -> None:
        if not self.kind or not self.reason:
            raise ValueError("排除范围必须记录类型和原因")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionReport:
    status: BoundaryStatus
    extractor_kind: str
    extractor_version: str
    excluded_ranges: tuple[ExcludedRange, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    source_coverage: SourceSpan | None = None

    def __post_init__(self) -> None:
        if self.status not in {"confirmed", "review_required", "rejected"}:
            raise ValueError("未知提取报告状态")
        if not self.extractor_kind or not self.extractor_version:
            raise ValueError("提取报告必须记录策略类型和版本")


@dataclass(frozen=True, slots=True, kw_only=True)
class LegalDocumentIntermediate:
    schema_version: str
    document_id: str
    source_ref: SourceRef
    extraction_class: ExtractionClass
    content_class: ContentClass
    target: TargetMetadata
    boundary: BoundaryDecision
    body_text: str
    body_units: tuple[BodyUnit, ...]
    diagnostics: tuple[str, ...]
    extraction_report: ExtractionReport

    def __post_init__(self) -> None:
        if not self.schema_version or not self.document_id:
            raise ValueError("中间格式必须包含版本和 document_id")


def validate_legal_intermediate(intermediate: LegalDocumentIntermediate) -> None:
    try:
        current_digest = sha256(
            intermediate.source_ref.source_path.read_bytes()
        ).hexdigest()
    except OSError as exc:
        raise ValueError("无法读取中间格式绑定的来源文件") from exc
    if current_digest != intermediate.source_ref.source_sha256:
        raise ValueError("中间格式绑定的来源摘要已变化")
    if intermediate.boundary.status != intermediate.extraction_report.status:
        raise ValueError("边界状态与提取报告状态不一致")

    if intermediate.boundary.status != "confirmed":
        if intermediate.body_text or intermediate.body_units:
            raise ValueError("非 confirmed 中间格式不得携带正文")
        return

    if intermediate.content_class is ContentClass.S4:
        raise ValueError("S4 不能形成 confirmed 中间格式")
    if not intermediate.body_text or not intermediate.body_units:
        raise ValueError("confirmed 中间格式正文不能为空")
    if intermediate.boundary.start is None or intermediate.boundary.end is None:
        raise ValueError("confirmed 中间格式必须包含边界")
    if intermediate.extraction_report.source_coverage is None:
        raise ValueError("confirmed 中间格式必须记录来源覆盖")

    expected_body = "\n".join(unit.text for unit in intermediate.body_units)
    if intermediate.body_text != expected_body:
        raise ValueError("body_text 必须由 body_units 按序组成")
    title_units = [
        unit for unit in intermediate.body_units if unit.kind == "title"
    ]
    if len(title_units) != 1 or title_units[0].text != intermediate.target.title:
        raise ValueError("正文必须包含唯一目标标题")
    if not any(unit.kind == "article" for unit in intermediate.body_units):
        raise ValueError("正文必须包含至少一个正式条文")

    previous_end: tuple[int, int] | None = None
    boundary_start = _position_key(intermediate.boundary.start, 0)
    boundary_end = _position_key(
        intermediate.boundary.end,
        intermediate.body_units[-1].source_span.end_char_offset,
    )
    for unit in intermediate.body_units:
        start = _span_start(unit.source_span)
        end = _span_end(unit.source_span)
        if previous_end is not None and start < previous_end:
            raise ValueError("正文单元来源位置必须单调")
        if start < boundary_start or end > boundary_end:
            raise ValueError("正文单元必须位于 confirmed 边界内")
        previous_end = end

    for excluded in intermediate.extraction_report.excluded_ranges:
        for unit in intermediate.body_units:
            if _spans_overlap(excluded.source_span, unit.source_span):
                raise ValueError("排除范围不得与正文来源范围重叠")

    coverage = intermediate.extraction_report.source_coverage
    if (
        _span_start(coverage) > _span_start(intermediate.body_units[0].source_span)
        or _span_end(coverage) < _span_end(intermediate.body_units[-1].source_span)
    ):
        raise ValueError("来源覆盖必须完整包含正文单元")


def write_confirmed_normalized(
    intermediate: LegalDocumentIntermediate,
    output_dir: Path,
) -> Path:
    if intermediate.boundary.status != "confirmed":
        raise ValueError("只有 confirmed 中间格式可以写入 normalized staging")
    validate_legal_intermediate(intermediate)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{intermediate.document_id}.txt"
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(intermediate.body_text)
    return output_path


def _position_key(location: SourceLocation, char_offset: int) -> tuple[int, int]:
    return (location.block_order, char_offset)


def _span_start(span: SourceSpan) -> tuple[int, int]:
    return _position_key(span.start, span.start_char_offset)


def _span_end(span: SourceSpan) -> tuple[int, int]:
    return _position_key(span.end, span.end_char_offset)


def _spans_overlap(first: SourceSpan, second: SourceSpan) -> bool:
    return _span_start(first) <= _span_end(second) and _span_start(
        second
    ) <= _span_end(first)
