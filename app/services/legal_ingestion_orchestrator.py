from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, cast
import uuid

from app.services.chunk_builder import build_intermediate_chunks, write_chunks
from app.services.corpus_ingestor import CorpusDocument
from app.services.incremental_import import (
    CommitPlan,
    CommittedImport,
    IncrementalImportError,
    IncrementalImportSummary,
    create_import_staging,
)
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.legal_extractor import (
    ExtractionRequest,
    ExtractionResult,
    validate_extraction_result,
)
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ContentClass,
    ExtractionClass,
    FrozenBatchInput,
    IngestionDisposition,
    IngestionInput,
    LegalSourceRecord,
    SourceRef,
)
from app.services.legal_intermediate import (
    LegalDocumentIntermediate,
    validate_legal_intermediate,
    write_confirmed_normalized,
)
from app.services.legal_quality_gates import (
    GateOutcome,
    QualityInput,
    QualityReport,
    evaluate_legal_quality,
)
from app.services.legal_qualified_import import (
    CommitQualification,
    QualifiedCommitPlan,
    commit_qualified_staged_import,
)
from app.services.legal_source_classifier import (
    classify_content_signals,
    classify_source,
    detect_content_signals,
)
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    CapabilityStatus,
    ExtractionStrategyRegistry,
    build_boundary_strategy_registry,
    build_extraction_strategy_registry,
)
from app.services.legal_word_extractor import WordLegalExtractor
from app.services.structure_parser import parse_legal_intermediate, write_structured_document


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
                expected_title=source.source_path.stem,
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
        boundary_disposition = IngestionDisposition.READY
        boundary_reason: str | None = None
        if isinstance(boundary_result, LegalDocumentIntermediate):
            try:
                validate_legal_intermediate(boundary_result)
            except ValueError:
                boundary_disposition = IngestionDisposition.FAILED
                boundary_reason = "boundary_invariant_failed"
            else:
                if boundary_result.boundary.status == "review_required":
                    boundary_disposition = IngestionDisposition.REVIEW_REQUIRED
                    boundary_reason = "boundary_review_required"
                elif boundary_result.boundary.status == "rejected":
                    boundary_disposition = IngestionDisposition.FAILED
                    boundary_reason = "boundary_rejected"
        return LegalIngestionOutcome(
            run_id=run_id,
            source=source,
            disposition=boundary_disposition,
            extraction_class=record.extraction_class,
            content_class=content_class,
            reason_code=boundary_reason,
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


def run_legal_ingestion(
    *,
    sources: Sequence[Path],
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
    staging_root: Path,
    embedder: object,
    run_id: str | None = None,
    classifier: Callable[[SourceRef], LegalSourceRecord] | None = None,
    extraction_registry: ExtractionStrategyRegistry | None = None,
    boundary_registry: BoundaryStrategyRegistry | None = None,
) -> IncrementalImportSummary:
    """统一法规摄取入口：分类、提取、边界、解析、切块、质量门禁、资格提交。

    每份来源独立处理，只有 ``auto_passed`` 质量结论才会进入串行 Append-Only 提交。
    失败只影响当前文件，不会回滚已经提交的文件。
    """
    actual_run_id = run_id or uuid.uuid4().hex
    classifier = classifier or classify_source
    extraction_registry = extraction_registry or build_extraction_strategy_registry(
        word_extractor=WordLegalExtractor()
    )
    boundary_registry = boundary_registry or build_boundary_strategy_registry(
        s1_strategy=S1BoundaryStrategy()
    )

    orchestrator = LegalIngestionOrchestrator(
        classifier=classifier,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    source_refs = tuple(_build_source_ref(path) for path in sources)
    ingestion_input = _build_ingestion_input(source_refs)
    outcomes = orchestrator.prepare(ingestion_input, run_id=actual_run_id)

    committed: list[CommittedImport] = []
    documents: list[CorpusDocument] = []
    for outcome in outcomes:
        if outcome.disposition is not IngestionDisposition.READY:
            raise IncrementalImportError(
                f"来源未进入 ready 状态: {outcome.source.relative_path}, "
                f"disposition={outcome.disposition.value}, reason={outcome.reason_code}"
            )
        committed_import = _commit_qualified_outcome(
            outcome=outcome,
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifest_path,
            staging_root=staging_root,
            embedder=embedder,
            run_id=actual_run_id,
        )
        committed.append(committed_import)
        documents.append(
            CorpusDocument(
                document_id=committed_import.document_id,
                source_path=outcome.source.source_path,
                source_name=outcome.source.source_path.stem,
                file_type=cast(Literal["doc", "docx"], outcome.source.declared_extension.lstrip(".")),
            )
        )

    return IncrementalImportSummary(
        run_id=actual_run_id,
        documents=documents,
        committed_document_ids=[item.document_id for item in committed],
        total_chunks=sum(item.chunk_count for item in committed),
        manifest_path=manifest_path,
    )


def _build_source_ref(path: Path) -> SourceRef:
    resolved = path.resolve()
    return SourceRef(
        relative_path=resolved.name,
        source_path=resolved,
        source_sha256=sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        declared_extension=resolved.suffix.lower(),
    )


def _build_ingestion_input(source_refs: tuple[SourceRef, ...]) -> IngestionInput:
    if len(source_refs) == 1:
        return IngestionInput(single_source=source_refs[0])

    sorted_refs = tuple(sorted(source_refs, key=lambda ref: ref.relative_path))
    batch_digest = sha256(
        "".join(
            f"{ref.relative_path}:{ref.source_sha256}" for ref in sorted_refs
        ).encode("utf-8")
    ).hexdigest()
    return IngestionInput(
        batch=FrozenBatchInput(
            root=sorted_refs[0].source_path.parent,
            sources=sorted_refs,
            batch_digest=batch_digest,
        )
    )


def _commit_qualified_outcome(
    *,
    outcome: LegalIngestionOutcome,
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
    staging_root: Path,
    embedder: object,
    run_id: str,
) -> CommittedImport:
    intermediate = outcome.boundary_result
    if not isinstance(intermediate, LegalDocumentIntermediate):
        raise IncrementalImportError(
            f"boundary_result 不是 LegalDocumentIntermediate: {outcome.source.relative_path}"
        )

    parsed = parse_legal_intermediate(intermediate)
    chunks = build_intermediate_chunks(intermediate, parsed)
    quality_input = QualityInput(
        source_sha256=intermediate.source_ref.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=intermediate.extraction_class,
        content_class=intermediate.content_class,
        source=intermediate.source_ref,
        extraction=outcome.extraction_result,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
    report = evaluate_legal_quality(quality_input)
    if report.overall is not GateOutcome.PASS:
        raise IncrementalImportError(
            f"质量门禁未通过: {intermediate.document_id}, overall={report.overall.value}"
        )

    staging = create_import_staging(staging_root, run_id=run_id)
    write_confirmed_normalized(intermediate, staging.normalized_dir)
    write_structured_document(parsed, staging.structured_dir)
    write_chunks(chunks, intermediate.document_id, staging.chunks_dir)

    attempt_id = f"{run_id}-{intermediate.document_id}"
    quality_report_path = staging.manifest_dir / f"{attempt_id}.quality.json"
    quality_report_path.write_text(
        json.dumps(_quality_report_as_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    normalized_path = staging.normalized_dir / f"{intermediate.document_id}.txt"
    structured_path = staging.structured_dir / f"{intermediate.document_id}.json"
    chunks_path = staging.chunks_dir / f"{intermediate.document_id}.jsonl"

    normalized_sha256 = sha256(normalized_path.read_bytes()).hexdigest()
    structured_sha256 = sha256(structured_path.read_bytes()).hexdigest()
    chunks_sha256 = sha256(chunks_path.read_bytes()).hexdigest()
    quality_report_sha256 = sha256(quality_report_path.read_bytes()).hexdigest()

    commit_plan = CommitPlan(
        document_id=intermediate.document_id,
        source_name=intermediate.source_ref.source_path.stem,
        source_path=str(intermediate.source_ref.source_path),
        source_file_type=cast(
            Literal["doc", "docx"],
            intermediate.source_ref.declared_extension.lstrip("."),
        ),
        chunk_count=len(chunks),
        staging=staging,
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=manifest_path,
        run_id=run_id,
    )
    qualification = CommitQualification(
        attempt_id=attempt_id,
        qualified_state="auto_passed",
        ruleset_version=report.ruleset_version,
        source_sha256=intermediate.source_ref.source_sha256,
        quality_report_sha256=quality_report_sha256,
        normalized_sha256=normalized_sha256,
        structured_sha256=structured_sha256,
        chunks_sha256=chunks_sha256,
    )
    qualified_plan = QualifiedCommitPlan(
        commit_plan=commit_plan,
        quality_report_path=quality_report_path,
        quality_report_sha256=quality_report_sha256,
        qualification=qualification,
    )
    return commit_qualified_staged_import(qualified_plan, embedder=embedder)


def _quality_report_as_dict(report: QualityReport) -> dict[str, Any]:
    return {
        "ruleset_version": report.ruleset_version,
        "source_sha256": report.source_sha256,
        "document_id": report.document_id,
        "overall": report.overall.value,
        "measured": report.measured,
        "gates": [
            {
                "gate_id": gate.gate_id,
                "outcome": gate.outcome.value,
                "measured": gate.measured,
                "evidence_refs": list(gate.evidence_refs),
                "reason_code": gate.reason_code,
            }
            for gate in report.gates
        ],
    }
