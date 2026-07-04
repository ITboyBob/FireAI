from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionRequest,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ContentSignals,
    ExtractionClass,
    IngestionDisposition,
    IngestionInput,
    LegalSourceClassification,
    LegalSourceRecord,
    SourceProbe,
    SourceRef,
)
from app.services.legal_ingestion_orchestrator import LegalIngestionOrchestrator
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    ExtractionStrategyRegistry,
    build_extraction_strategy_registry,
    build_boundary_strategy_registry,
)
from app.services.legal_textutil import TextutilRunResult
from app.services.legal_word_extractor import WordLegalExtractor
from app.services.corpus_ingestor import build_document_id
from app.services.incremental_import import CommitPlan, ImportStaging
from app.services.legal_intermediate import (
    BoundaryDecision,
    ExtractionReport,
    LegalDocumentIntermediate,
    SourceSpan,
    TargetMetadata,
)
from app.services.legal_ingestion_orchestrator import run_legal_ingestion
from app.services.legal_qualified_import import CommitQualification
from app.services.legal_quality_gates import GateOutcome, QualityReport
from app.services.legal_s2_boundary import S2BoundaryStrategy
from app.services.legal_s3_boundary import S3BoundaryStrategy


def _record(
    tmp_path: Path,
    *,
    content_class=ContentClass.S1,
    disposition=ClassificationDisposition.READY,
    source_name: str = "sample",
):
    source_path = tmp_path / f"{source_name}.doc"
    source_path.write_bytes(b"sample")
    digest = sha256(b"sample").hexdigest()
    source = SourceRef(
        relative_path=f"{source_name}.doc",
        source_path=source_path,
        source_sha256=digest,
        size_bytes=6,
        declared_extension=".doc",
    )
    evidence = ClassificationEvidence(
        source_sha256=digest,
        signature_kind="ole_doc",
        detected_mime_type="application/msword",
        declared_extension=".doc",
        conversion_succeeded=True,
        converted_character_count=20,
    )
    return LegalSourceRecord(
        source=source,
        probe=SourceProbe(
            source_sha256=digest,
            signature_kind="ole_doc",
            detected_mime_type="application/msword",
            declared_extension=".doc",
            readable=True,
        ),
        classification=LegalSourceClassification(
            extraction_class=ExtractionClass.W,
            content_class=content_class,
            disposition=disposition,
            evidence=evidence,
            content_signals=ContentSignals(
                candidate_extracted=True,
                title_count=1,
                article_marker_count=1,
            ),
        ),
    )


@dataclass(frozen=True)
class FakeExtractor:
    kind: str = "W"
    version: str = "fake-v1"
    source_sha256_override: str | None = None
    raises: bool = False
    lines: tuple[str, ...] = ("某规定", "第一条 正文")

    def extract(self, request: ExtractionRequest):
        if self.raises:
            raise RuntimeError("deterministic tool failure")
        digest = self.source_sha256_override or request.source.source_sha256
        blocks = tuple(
            ExtractedBlock(
                order=order,
                text=line,
                location=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=order,
                    line_number=order + 1,
                ),
            )
            for order, line in enumerate(self.lines)
        )
        return ExtractionResult(
            source_sha256=digest,
            extractor_kind=self.kind,
            extractor_version=self.version,
            pages=(
                ExtractedPage(
                    logical_page=1,
                    page_number=None,
                    block_orders=tuple(range(len(blocks))),
                ),
            ),
            text_blocks=blocks,
            disposition=IngestionDisposition.READY,
        )


@dataclass(frozen=True)
class FakeBoundary:
    kind: str = "S1"
    version: str = "fake-v1"

    def identify(self, extraction, *, source, expected_title=None):
        return {"status": "confirmed", "source_sha256": source.source_sha256}


@dataclass(frozen=True)
class FakeS2ReviewBoundary:
    kind: str = "S2"
    version: str = "fake-v1"
    status: str = "review_required"
    reason: str = "test_review"

    def identify(self, extraction, *, source, expected_title=None):
        title = expected_title or source.source_path.stem
        location = SourceLocation(
            logical_page=1,
            page_number=None,
            block_order=0,
            line_number=1,
        )
        span = SourceSpan(
            start=location,
            end=location,
            start_char_offset=0,
            end_char_offset=0,
        )
        target = TargetMetadata(title=title)
        boundary = BoundaryDecision(
            status=self.status,
            start=None,
            end=None,
            ambiguities=(self.reason,),
        )
        report = ExtractionReport(
            status=self.status,
            extractor_kind=extraction.extractor_kind,
            extractor_version=extraction.extractor_version,
            warnings=(),
        )
        return LegalDocumentIntermediate(
            schema_version="legal-intermediate-v2",
            document_id=build_document_id(title),
            source_ref=source,
            extraction_class=ExtractionClass(extraction.extractor_kind),
            content_class=ContentClass.S2,
            target=target,
            boundary=boundary,
            body_text="",
            body_units=(),
            diagnostics=(self.reason,),
            extraction_report=report,
        )


def test_default_orchestrator_returns_unsupported_without_writes(tmp_path, monkeypatch):
    record = _record(tmp_path)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("blocked outcome must not write")

    monkeypatch.setattr(
        "app.services.incremental_import.run_incremental_import",
        forbidden,
    )
    monkeypatch.setattr(
        "app.services.incremental_import.commit_staged_import",
        forbidden,
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=ExtractionStrategyRegistry(),
        boundary_registry=BoundaryStrategyRegistry(),
    )

    outcomes = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-123",
    )

    assert len(outcomes) == 1
    assert outcomes[0].disposition is IngestionDisposition.UNSUPPORTED
    assert outcomes[0].extraction_class is ExtractionClass.W
    assert outcomes[0].content_class is ContentClass.S1
    assert calls == []
    assert not hasattr(orchestrator, "writer")
    assert not (tmp_path / "data" / ".staging").exists()


def test_orchestrator_resolves_axes_independently_and_returns_ready(tmp_path):
    record = _record(tmp_path)
    extraction_registry = ExtractionStrategyRegistry()
    boundary_registry = BoundaryStrategyRegistry()
    extraction_registry.register(ExtractionClass.W, FakeExtractor())
    boundary_registry.register(ContentClass.S1, FakeBoundary())
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-123",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    assert outcome.extraction_class is ExtractionClass.W
    assert outcome.content_class is ContentClass.S1
    assert outcome.boundary_result["status"] == "confirmed"


def test_orchestrator_runs_word_then_stops_at_unsupported_s1_boundary(tmp_path):
    record = _record(tmp_path)
    word = WordLegalExtractor(
        run_textutil=lambda source: TextutilRunResult(
            returncode=0,
            stdout="某规定\n第一条 正文",
            stderr="",
        )
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=build_extraction_strategy_registry(
            word_extractor=word
        ),
        boundary_registry=BoundaryStrategyRegistry(),
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-123",
    )[0]

    assert outcome.disposition is IngestionDisposition.UNSUPPORTED
    assert outcome.reason_code == "boundary_strategy_unsupported"
    assert outcome.extraction_result.extractor_kind == "W"


def test_orchestrator_combines_word_and_s1_without_combination_handler(tmp_path):
    record = _record(tmp_path)
    word = WordLegalExtractor(
        run_textutil=lambda source: TextutilRunResult(
            returncode=0,
            stdout="sample\n第一条 正文",
            stderr="",
        )
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=build_extraction_strategy_registry(
            word_extractor=word
        ),
        boundary_registry=build_boundary_strategy_registry(
            s1_strategy=S1BoundaryStrategy()
        ),
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-123",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    assert outcome.boundary_result.boundary.status == "confirmed"
    assert outcome.extraction_class is ExtractionClass.W
    assert outcome.content_class is ContentClass.S1


def test_orchestrator_maps_strategy_exception_and_digest_mismatch_to_failed(tmp_path):
    record = _record(tmp_path)

    for extractor, expected_code in (
        (FakeExtractor(raises=True), "extraction_strategy_failed"),
        (FakeExtractor(source_sha256_override="f" * 64), "extraction_invariant_failed"),
    ):
        extraction_registry = ExtractionStrategyRegistry()
        extraction_registry.register(ExtractionClass.W, extractor)
        orchestrator = LegalIngestionOrchestrator(
            classifier=lambda source: record,
            extraction_registry=extraction_registry,
            boundary_registry=BoundaryStrategyRegistry(),
        )

        outcome = orchestrator.prepare(
            IngestionInput(single_source=record.source),
            run_id="run-123",
        )[0]

        assert outcome.disposition is IngestionDisposition.FAILED
        assert outcome.reason_code == expected_code


def test_orchestrator_short_circuits_s4_classification_review(tmp_path):
    record = _record(
        tmp_path,
        content_class=ContentClass.S4,
        disposition=ClassificationDisposition.REVIEW_REQUIRED,
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=ExtractionStrategyRegistry(),
        boundary_registry=BoundaryStrategyRegistry(),
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-123",
    )[0]

    assert outcome.disposition is IngestionDisposition.REVIEW_REQUIRED
    assert outcome.reason_code == "classification_review_required"


S2_LINES = (
    "某省人民政府",
    "关于修改《某规定》的决定",
    "某规定",
    "（2020年1月1日公布）",
    "第一章 总则",
    "第一条 正文。",
    "第二章 分则",
    "第二条 末条。",
)


S3_LINES = (
    "某规定",
    "第一条 正文。",
    "第二条 末条。",
    "",
    "某机关 2026年6月29日印发",
    "",
    "附件：",
    "",
    "行政执法监督文书1：",
    "审批表",
    "姓名：",
    "单位：",
)


def test_orchestrator_resolves_w_s2_axes(tmp_path):
    record = _record(tmp_path, content_class=ContentClass.S2, source_name="某规定")
    extraction_registry = build_extraction_strategy_registry(
        word_extractor=FakeExtractor(lines=S2_LINES)
    )
    boundary_registry = build_boundary_strategy_registry(
        s1_strategy=S1BoundaryStrategy(),
        s2_strategy=S2BoundaryStrategy(),
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-s2",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    assert outcome.extraction_class is ExtractionClass.W
    assert outcome.content_class is ContentClass.S2
    assert isinstance(outcome.boundary_result, LegalDocumentIntermediate)
    assert outcome.boundary_result.content_class is ContentClass.S2
    assert outcome.boundary_result.boundary.status == "confirmed"


def test_orchestrator_resolves_w_s3_axes(tmp_path):
    record = _record(tmp_path, content_class=ContentClass.S3, source_name="某规定")
    extraction_registry = build_extraction_strategy_registry(
        word_extractor=FakeExtractor(lines=S3_LINES)
    )
    boundary_registry = build_boundary_strategy_registry(
        s1_strategy=S1BoundaryStrategy(),
        s2_strategy=S2BoundaryStrategy(),
        s3_strategy=S3BoundaryStrategy(),
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=lambda source: record,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=record.source),
        run_id="run-s3",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    assert outcome.extraction_class is ExtractionClass.W
    assert outcome.content_class is ContentClass.S3
    assert isinstance(outcome.boundary_result, LegalDocumentIntermediate)
    assert outcome.boundary_result.content_class is ContentClass.S3
    assert outcome.boundary_result.boundary.status == "confirmed"


def test_run_legal_ingestion_dry_run_skips_downstream_for_s2_review(
    tmp_path, monkeypatch
):
    record = _record(tmp_path, content_class=ContentClass.S2)
    extraction_registry = build_extraction_strategy_registry(
        word_extractor=FakeExtractor(lines=S2_LINES)
    )
    boundary_registry = build_boundary_strategy_registry(
        s2_strategy=FakeS2ReviewBoundary()
    )
    calls = []

    def fake_evaluate(*, outcome, **kwargs):
        calls.append(outcome)
        raise AssertionError("must not evaluate non-ready S2 outcome")

    monkeypatch.setattr(
        "app.services.legal_ingestion_orchestrator._evaluate_qualified_outcome",
        fake_evaluate,
    )

    summary = run_legal_ingestion(
        sources=[record.source.source_path],
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "index",
        manifest_path=tmp_path / "manifest.json",
        staging_root=tmp_path / "staging",
        embedder=object(),
        run_id="run-s2-review",
        dry_run=True,
        classifier=lambda source: record,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    assert not calls
    assert summary.batch_report_path is not None


def test_run_legal_ingestion_dry_run_skips_downstream_for_s3_review(
    tmp_path, monkeypatch
):
    record = _record(tmp_path, content_class=ContentClass.S3)
    extraction_registry = build_extraction_strategy_registry(
        word_extractor=FakeExtractor(lines=S3_LINES[:4])
    )
    boundary_registry = build_boundary_strategy_registry(
        s3_strategy=FakeS2ReviewBoundary(kind="S3")
    )
    calls = []

    def fake_evaluate(*, outcome, **kwargs):
        calls.append(outcome)
        raise AssertionError("must not evaluate non-ready S3 outcome")

    monkeypatch.setattr(
        "app.services.legal_ingestion_orchestrator._evaluate_qualified_outcome",
        fake_evaluate,
    )

    summary = run_legal_ingestion(
        sources=[record.source.source_path],
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "index",
        manifest_path=tmp_path / "manifest.json",
        staging_root=tmp_path / "staging",
        embedder=object(),
        run_id="run-s3-review",
        dry_run=True,
        classifier=lambda source: record,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    assert not calls
    assert summary.batch_report_path is not None
