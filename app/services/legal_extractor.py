from dataclasses import dataclass, field
from typing import Protocol

from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    LegalSourceRecord,
    SourceRef,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionRequest:
    source: SourceRef
    extraction_class: ExtractionClass
    classification_evidence: ClassificationEvidence
    run_id: str

    def __post_init__(self) -> None:
        if self.extraction_class is ExtractionClass.PX:
            raise ValueError("PX 不能进入自动提取策略")
        if self.source.source_sha256 != self.classification_evidence.source_sha256:
            raise ValueError("提取请求的来源摘要与分类证据摘要不一致")
        if not self.run_id.strip():
            raise ValueError("提取请求必须携带非空 run_id")

    @classmethod
    def from_source_record(
        cls,
        record: LegalSourceRecord,
        *,
        run_id: str,
    ) -> "ExtractionRequest":
        if record.extraction_class is ExtractionClass.PX:
            raise ValueError("PX 不能进入自动提取策略")
        if record.classification.disposition is not ClassificationDisposition.READY:
            raise ValueError("分类证据未达到自动提取条件")
        return cls(
            source=record.source,
            extraction_class=record.extraction_class,
            classification_evidence=record.classification.evidence,
            run_id=run_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceLocation:
    logical_page: int
    page_number: int | None
    block_order: int
    line_number: int | None

    def __post_init__(self) -> None:
        if self.logical_page < 1:
            raise ValueError("逻辑页必须从 1 开始")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("物理页码必须为正整数")
        if self.block_order < 0:
            raise ValueError("块顺序不能为负数")
        if self.line_number is not None and self.line_number < 1:
            raise ValueError("行号必须为正整数")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractedBlock:
    order: int
    text: str
    location: SourceLocation

    def __post_init__(self) -> None:
        if self.order < 0:
            raise ValueError("提取块顺序不能为负数")
        if self.order != self.location.block_order:
            raise ValueError("提取块顺序必须与来源位置一致")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractedPage:
    logical_page: int
    page_number: int | None
    block_orders: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.logical_page < 1:
            raise ValueError("逻辑页必须从 1 开始")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("物理页码必须为正整数")
        if any(order < 0 for order in self.block_orders):
            raise ValueError("页面块顺序不能为负数")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionFailure:
    stage: str
    code: str
    message: str
    retryable: bool

    def __post_init__(self) -> None:
        if not self.stage or not self.code or not self.message:
            raise ValueError("extraction failure 必须包含阶段、错误码和说明")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionResult:
    source_sha256: str
    extractor_kind: str
    extractor_version: str
    pages: tuple[ExtractedPage, ...]
    text_blocks: tuple[ExtractedBlock, ...]
    disposition: IngestionDisposition
    metrics: tuple[tuple[str, int | float | str], ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    failure: ExtractionFailure | None = None

    def __post_init__(self) -> None:
        if not self.extractor_kind or not self.extractor_version:
            raise ValueError("提取结果必须包含策略类型与版本")
        if (
            self.disposition is IngestionDisposition.FAILED
            and self.failure is None
        ):
            raise ValueError("failed 提取结果必须携带 failure")
        if (
            self.disposition is not IngestionDisposition.FAILED
            and self.failure is not None
        ):
            raise ValueError("非 failed 提取结果不能携带 failure")
        if self.disposition is IngestionDisposition.READY and (
            not self.pages or not self.text_blocks
        ):
            raise ValueError("ready 提取结果必须包含页面和文本块")


class LegalExtractor(Protocol):
    kind: str
    version: str

    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...


class LegalBoundaryStrategy(Protocol):
    kind: str
    version: str

    def identify(
        self,
        extraction: ExtractionResult,
        *,
        source: SourceRef,
        expected_title: str | None = None,
    ) -> object: ...


def validate_extraction_result(
    request: ExtractionRequest,
    result: ExtractionResult,
) -> None:
    if request.source.source_sha256 != result.source_sha256:
        raise ValueError("提取结果来源摘要与请求摘要不一致")
    if result.extractor_kind != request.extraction_class.value:
        raise ValueError("提取结果策略类型与请求提取轴不一致")

    block_orders = tuple(block.order for block in result.text_blocks)
    if block_orders != tuple(range(len(result.text_blocks))):
        raise ValueError("提取块顺序必须从 0 开始连续递增")

    page_numbers = tuple(page.logical_page for page in result.pages)
    if page_numbers != tuple(sorted(set(page_numbers))):
        raise ValueError("逻辑页必须唯一并连续递增")
    if page_numbers and page_numbers != tuple(range(1, len(page_numbers) + 1)):
        raise ValueError("逻辑页必须从 1 开始连续递增")

    page_block_orders = tuple(
        order for page in result.pages for order in page.block_orders
    )
    if page_block_orders != block_orders:
        raise ValueError("页面声明的块顺序必须完整覆盖连续提取块")
    page_by_order = {
        order: page.logical_page
        for page in result.pages
        for order in page.block_orders
    }
    if any(
        block.location.logical_page != page_by_order[block.order]
        for block in result.text_blocks
    ):
        raise ValueError("提取块来源位置必须与页面归属一致")
