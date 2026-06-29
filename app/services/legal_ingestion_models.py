from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
import re


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ExtractionClass(str, Enum):
    W = "W"
    PT = "PT"
    PS = "PS"
    PX = "PX"


class ContentClass(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


class ClassificationDisposition(str, Enum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class IngestionDisposition(str, Enum):
    READY = "ready"
    UNSUPPORTED = "unsupported"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"

    @property
    def may_carry_commit_qualification(self) -> bool:
        return self is IngestionDisposition.READY


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceRef:
    relative_path: str
    source_path: Path
    source_sha256: str
    size_bytes: int
    declared_extension: str

    def __post_init__(self) -> None:
        relative = PurePosixPath(self.relative_path)
        if (
            not self.relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in self.relative_path
        ):
            raise ValueError("来源相对路径必须是安全的 POSIX 相对路径")
        if not self.source_path.is_absolute():
            raise ValueError("来源绝对路径必须是绝对路径")
        _validate_sha256(self.source_sha256, field_name="来源摘要")
        if self.size_bytes < 0:
            raise ValueError("来源文件大小不能为负数")
        _validate_declared_extension(self.declared_extension)


@dataclass(frozen=True, slots=True, kw_only=True)
class FrozenBatchInput:
    root: Path
    sources: tuple[SourceRef, ...]
    batch_digest: str

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ValueError("批次根目录必须是绝对路径")
        if not self.sources:
            raise ValueError("冻结批次必须至少包含一个来源")
        relative_paths = tuple(item.relative_path for item in self.sources)
        if relative_paths != tuple(sorted(relative_paths)):
            raise ValueError("冻结批次来源必须按相对路径稳定排序")
        if len(relative_paths) != len(set(relative_paths)):
            raise ValueError("冻结批次不能包含重复相对路径")
        _validate_sha256(self.batch_digest, field_name="批次摘要")


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionInput:
    single_source: SourceRef | None = None
    batch: FrozenBatchInput | None = None

    def __post_init__(self) -> None:
        if (self.single_source is None) == (self.batch is None):
            raise ValueError("单文件与冻结批次必须恰好选择一种输入模式")


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassificationEvidence:
    source_sha256: str
    signature_kind: str | None
    detected_mime_type: str | None
    declared_extension: str
    conversion_succeeded: bool | None = None
    converted_character_count: int | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_sha256(self.source_sha256, field_name="分类证据来源摘要")
        _validate_declared_extension(self.declared_extension)
        if self.converted_character_count is not None and self.converted_character_count < 0:
            raise ValueError("转换字符数不能为负数")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceProbe:
    source_sha256: str
    signature_kind: str | None
    detected_mime_type: str | None
    declared_extension: str
    readable: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_sha256(self.source_sha256, field_name="探针来源摘要")
        _validate_declared_extension(self.declared_extension)


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentSignals:
    candidate_extracted: bool
    title_count: int
    article_marker_count: int
    has_leading_material: bool = False
    has_trailing_material: bool = False
    has_interleaved_material: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.title_count < 0 or self.article_marker_count < 0:
            raise ValueError("内容信号计数不能为负数")


@dataclass(frozen=True, slots=True, kw_only=True)
class LegalSourceClassification:
    extraction_class: ExtractionClass
    content_class: ContentClass | None
    disposition: ClassificationDisposition
    evidence: ClassificationEvidence
    content_signals: ContentSignals | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (
            self.extraction_class is ExtractionClass.PX
            and self.disposition is ClassificationDisposition.READY
        ):
            raise ValueError("PX 分类不能进入 ready 状态")
        if (
            self.content_class is ContentClass.S4
            and self.disposition is ClassificationDisposition.READY
        ):
            raise ValueError("S4 内容分类必须进入人工复核")
        if (
            self.disposition is ClassificationDisposition.READY
            and self.content_signals is not None
            and self.content_signals.candidate_extracted
            and self.content_class is None
        ):
            raise ValueError("候选文本已提取时必须完成内容分类")


@dataclass(frozen=True, slots=True, kw_only=True)
class LegalSourceRecord:
    source: SourceRef
    probe: SourceProbe
    classification: LegalSourceClassification

    def __post_init__(self) -> None:
        digests = {
            self.source.source_sha256,
            self.probe.source_sha256,
            self.classification.evidence.source_sha256,
        }
        if len(digests) != 1:
            raise ValueError("来源、探针与分类证据摘要必须一致")
        if self.source.declared_extension != self.probe.declared_extension:
            raise ValueError("来源与探针声明扩展名必须一致")

    @property
    def extraction_class(self) -> ExtractionClass:
        return self.classification.extraction_class

    @property
    def content_class(self) -> ContentClass | None:
        return self.classification.content_class


def _validate_sha256(value: str, *, field_name: str) -> None:
    if not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name}必须是小写 SHA-256 十六进制字符串")


def _validate_declared_extension(value: str) -> None:
    if value and (
        not value.startswith(".")
        or value != value.lower()
        or "/" in value
        or "\\" in value
    ):
        raise ValueError("声明扩展名必须是以点开头的小写扩展名")
