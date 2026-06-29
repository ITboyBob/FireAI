from dataclasses import dataclass
from enum import Enum

from app.services.legal_extractor import LegalBoundaryStrategy, LegalExtractor
from app.services.legal_ingestion_models import ContentClass, ExtractionClass


class CapabilityStatus(str, Enum):
    IMPLEMENTED = "implemented"
    UNSUPPORTED = "unsupported"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyResolution:
    key: ExtractionClass | ContentClass
    status: CapabilityStatus
    strategy: LegalExtractor | LegalBoundaryStrategy | None = None
    reason_code: str | None = None


class ExtractionStrategyRegistry:
    def __init__(self) -> None:
        self._resolutions: dict[ExtractionClass, StrategyResolution] = {
            key: StrategyResolution(
                key=key,
                status=CapabilityStatus.UNSUPPORTED,
                reason_code="extraction_strategy_unsupported",
            )
            for key in (ExtractionClass.W, ExtractionClass.PT, ExtractionClass.PS)
        }

    def register(
        self,
        key: ExtractionClass,
        strategy: LegalExtractor,
    ) -> None:
        _validate_extraction_key(key)
        if strategy.kind != key.value:
            raise ValueError("提取策略 kind 必须与提取轴键一致")
        if self._resolutions[key].status is CapabilityStatus.IMPLEMENTED:
            raise ValueError(f"提取策略已注册: {key.value}")
        self._resolutions[key] = StrategyResolution(
            key=key,
            status=CapabilityStatus.IMPLEMENTED,
            strategy=strategy,
        )

    def resolve(self, key: ExtractionClass) -> StrategyResolution:
        _validate_extraction_key(key)
        return self._resolutions[key]


def build_extraction_strategy_registry(
    *,
    word_extractor: LegalExtractor | None = None,
) -> ExtractionStrategyRegistry:
    registry = ExtractionStrategyRegistry()
    if word_extractor is not None:
        registry.register(ExtractionClass.W, word_extractor)
    return registry


class BoundaryStrategyRegistry:
    def __init__(self) -> None:
        self._resolutions: dict[ContentClass, StrategyResolution] = {
            ContentClass.S1: StrategyResolution(
                key=ContentClass.S1,
                status=CapabilityStatus.UNSUPPORTED,
                reason_code="boundary_strategy_unsupported",
            ),
            ContentClass.S2: StrategyResolution(
                key=ContentClass.S2,
                status=CapabilityStatus.UNSUPPORTED,
                reason_code="boundary_strategy_unsupported",
            ),
            ContentClass.S3: StrategyResolution(
                key=ContentClass.S3,
                status=CapabilityStatus.UNSUPPORTED,
                reason_code="boundary_strategy_unsupported",
            ),
            ContentClass.S4: StrategyResolution(
                key=ContentClass.S4,
                status=CapabilityStatus.REVIEW_REQUIRED,
                reason_code="boundary_strategy_review_required",
            ),
        }

    def register(
        self,
        key: ContentClass,
        strategy: LegalBoundaryStrategy,
    ) -> None:
        _validate_boundary_key(key)
        if strategy.kind != key.value:
            raise ValueError("正文边界策略 kind 必须与内容轴键一致")
        if self._resolutions[key].status is CapabilityStatus.IMPLEMENTED:
            raise ValueError(f"正文边界策略已注册: {key.value}")
        self._resolutions[key] = StrategyResolution(
            key=key,
            status=CapabilityStatus.IMPLEMENTED,
            strategy=strategy,
        )

    def resolve(self, key: ContentClass) -> StrategyResolution:
        _validate_boundary_key(key)
        return self._resolutions[key]


def _validate_extraction_key(key: object) -> None:
    if not isinstance(key, ExtractionClass):
        raise TypeError("提取策略键必须是 ExtractionClass")
    if key is ExtractionClass.PX:
        raise ValueError("提取策略注册表不接受 PX")


def _validate_boundary_key(key: object) -> None:
    if not isinstance(key, ContentClass):
        raise TypeError("正文边界策略键必须是 ContentClass")
