from collections.abc import Callable
from dataclasses import dataclass

from app.services.legal_extractor import (
    ExtractionRequest,
    ExtractionResult,
    validate_extraction_result,
)
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    IngestionInput,
    LegalSourceRecord,
    SourceRef,
)
from app.services.legal_source_classifier import (
    classify_content_signals,
    detect_content_signals,
)
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    CapabilityStatus,
    ExtractionStrategyRegistry,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class LegalIngestionOutcome:
    run_id: str
    source: SourceRef
    disposition: IngestionDisposition
    extraction_class: ExtractionClass | None
    content_class: ContentClass | None
    reason_code: str | None = None
    extraction_result: ExtractionResult | None = None
    boundary_result: object | None = None


class LegalIngestionOrchestrator:
    def __init__(
        self,
        *,
        classifier: Callable[[SourceRef], LegalSourceRecord],
        extraction_registry: ExtractionStrategyRegistry,
        boundary_registry: BoundaryStrategyRegistry,
    ) -> None:
        self._classifier = classifier
        self._extraction_registry = extraction_registry
        self._boundary_registry = boundary_registry

    def prepare(
        self,
        ingestion_input: IngestionInput,
        *,
        run_id: str,
    ) -> tuple[LegalIngestionOutcome, ...]:
        if not run_id.strip():
            raise ValueError("统一编排必须携带非空 run_id")
        sources = (
            (ingestion_input.single_source,)
            if ingestion_input.single_source is not None
            else ingestion_input.batch.sources
        )
        return tuple(self._prepare_source(source, run_id=run_id) for source in sources)

    def _prepare_source(
        self,
        source: SourceRef,
        *,
        run_id: str,
    ) -> LegalIngestionOutcome:
        try:
            record = self._classifier(source)
        except Exception:
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                reason_code="classification_failed",
            )
        if (
            record.source.relative_path != source.relative_path
            or record.source.source_sha256 != source.source_sha256
        ):
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                reason_code="classification_source_mismatch",
            )
        if record.classification.disposition is ClassificationDisposition.FAILED:
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                reason_code="classification_failed",
                record=record,
            )
        if (
            record.classification.disposition
            is ClassificationDisposition.REVIEW_REQUIRED
        ):
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.REVIEW_REQUIRED,
                reason_code="classification_review_required",
                record=record,
            )

        extraction_resolution = self._extraction_registry.resolve(
            record.extraction_class
        )
        if extraction_resolution.status is not CapabilityStatus.IMPLEMENTED:
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=_status_disposition(extraction_resolution.status),
                reason_code=extraction_resolution.reason_code,
                record=record,
            )

        request = ExtractionRequest.from_source_record(record, run_id=run_id)
        try:
            extraction_result = extraction_resolution.strategy.extract(request)
        except Exception:
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                reason_code="extraction_strategy_failed",
                record=record,
            )
        try:
            validate_extraction_result(request, extraction_result)
        except ValueError:
            return _blocked_outcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                reason_code="extraction_invariant_failed",
                record=record,
            )
        if extraction_result.disposition is not IngestionDisposition.READY:
            return LegalIngestionOutcome(
                run_id=run_id,
                source=source,
                disposition=extraction_result.disposition,
                extraction_class=record.extraction_class,
                content_class=record.content_class,
                reason_code="extraction_not_ready",
                extraction_result=extraction_result,
            )

        candidate_text = "\n".join(
            block.text for block in extraction_result.text_blocks
        )
        content_class = classify_content_signals(
            detect_content_signals(candidate_text)
        )
        if (
            record.content_class is not None
            and record.content_class is not content_class
        ):
            return LegalIngestionOutcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.REVIEW_REQUIRED,
                extraction_class=record.extraction_class,
                content_class=content_class,
                reason_code="content_classification_changed",
                extraction_result=extraction_result,
            )

        boundary_resolution = self._boundary_registry.resolve(content_class)
        if boundary_resolution.status is not CapabilityStatus.IMPLEMENTED:
            return LegalIngestionOutcome(
                run_id=run_id,
                source=source,
                disposition=_status_disposition(boundary_resolution.status),
                extraction_class=record.extraction_class,
                content_class=content_class,
                reason_code=boundary_resolution.reason_code,
                extraction_result=extraction_result,
            )
        try:
            boundary_result = boundary_resolution.strategy.identify(
                extraction_result,
                source=source,
            )
        except Exception:
            return LegalIngestionOutcome(
                run_id=run_id,
                source=source,
                disposition=IngestionDisposition.FAILED,
                extraction_class=record.extraction_class,
                content_class=content_class,
                reason_code="boundary_strategy_failed",
                extraction_result=extraction_result,
            )
        return LegalIngestionOutcome(
            run_id=run_id,
            source=source,
            disposition=IngestionDisposition.READY,
            extraction_class=record.extraction_class,
            content_class=content_class,
            extraction_result=extraction_result,
            boundary_result=boundary_result,
        )


def _blocked_outcome(
    *,
    run_id: str,
    source: SourceRef,
    disposition: IngestionDisposition,
    reason_code: str | None,
    record: LegalSourceRecord | None = None,
) -> LegalIngestionOutcome:
    return LegalIngestionOutcome(
        run_id=run_id,
        source=source,
        disposition=disposition,
        extraction_class=record.extraction_class if record else None,
        content_class=record.content_class if record else None,
        reason_code=reason_code,
    )


def _status_disposition(status: CapabilityStatus) -> IngestionDisposition:
    if status is CapabilityStatus.UNSUPPORTED:
        return IngestionDisposition.UNSUPPORTED
    if status is CapabilityStatus.REVIEW_REQUIRED:
        return IngestionDisposition.REVIEW_REQUIRED
    raise ValueError("implemented 状态不能映射为阻断结果")
