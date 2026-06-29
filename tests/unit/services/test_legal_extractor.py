from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionFailure,
    ExtractionRequest,
    ExtractionResult,
    SourceLocation,
    validate_extraction_result,
)
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ContentSignals,
    ExtractionClass,
    IngestionDisposition,
    LegalSourceClassification,
    LegalSourceRecord,
    SourceProbe,
    SourceRef,
)


def _record(tmp_path: Path, *, extraction_class=ExtractionClass.W):
    source_path = tmp_path / "sample.doc"
    source_path.write_bytes(b"sample")
    digest = sha256(b"sample").hexdigest()
    source = SourceRef(
        relative_path="sample.doc",
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
            extraction_class=extraction_class,
            content_class=ContentClass.S1,
            disposition=(
                ClassificationDisposition.REVIEW_REQUIRED
                if extraction_class is ExtractionClass.PX
                else ClassificationDisposition.READY
            ),
            evidence=evidence,
            content_signals=ContentSignals(
                candidate_extracted=True,
                title_count=1,
                article_marker_count=1,
            ),
        ),
    )


def _valid_result(request: ExtractionRequest) -> ExtractionResult:
    blocks = (
        ExtractedBlock(
            order=0,
            text="某规定",
            location=SourceLocation(
                logical_page=1,
                page_number=None,
                block_order=0,
                line_number=1,
            ),
        ),
        ExtractedBlock(
            order=1,
            text="第一条 正文",
            location=SourceLocation(
                logical_page=1,
                page_number=None,
                block_order=1,
                line_number=2,
            ),
        ),
    )
    return ExtractionResult(
        source_sha256=request.source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=(0, 1),
            ),
        ),
        text_blocks=blocks,
        metrics=(("character_count", 8),),
        warnings=("physical_pagination_unknown",),
        disposition=IngestionDisposition.READY,
    )


def test_extraction_request_carries_source_evidence_and_run_id_without_s_axis(
    tmp_path,
):
    record = _record(tmp_path)

    request = ExtractionRequest.from_source_record(record, run_id="run-123")

    assert request.source is record.source
    assert request.extraction_class is ExtractionClass.W
    assert request.classification_evidence is record.classification.evidence
    assert request.run_id == "run-123"
    assert not hasattr(request, "content_class")
    assert not hasattr(request, "output_path")


def test_extraction_request_rejects_px_and_digest_mismatch(tmp_path):
    with pytest.raises(ValueError, match="PX"):
        ExtractionRequest.from_source_record(
            _record(tmp_path, extraction_class=ExtractionClass.PX),
            run_id="run-123",
        )

    record = _record(tmp_path)
    mismatched = ClassificationEvidence(
        source_sha256="f" * 64,
        signature_kind="ole_doc",
        detected_mime_type="application/msword",
        declared_extension=".doc",
        conversion_succeeded=True,
        converted_character_count=20,
    )
    with pytest.raises(ValueError, match="摘要"):
        ExtractionRequest(
            source=record.source,
            extraction_class=ExtractionClass.W,
            classification_evidence=mismatched,
            run_id="run-123",
        )


def test_validate_extraction_result_accepts_stable_page_and_block_order(tmp_path):
    request = ExtractionRequest.from_source_record(_record(tmp_path), run_id="run-123")
    result = _valid_result(request)

    validate_extraction_result(request, result)

    assert [block.order for block in result.text_blocks] == [0, 1]
    assert result.pages[0].block_orders == (0, 1)
    assert not hasattr(result, "output_path")
    assert not hasattr(result, "commit")


def test_validate_extraction_result_rejects_digest_and_order_invariants(tmp_path):
    request = ExtractionRequest.from_source_record(_record(tmp_path), run_id="run-123")
    valid = _valid_result(request)

    with pytest.raises(ValueError, match="摘要"):
        validate_extraction_result(
            request,
            ExtractionResult(
                source_sha256="f" * 64,
                extractor_kind=valid.extractor_kind,
                extractor_version=valid.extractor_version,
                pages=valid.pages,
                text_blocks=valid.text_blocks,
                disposition=IngestionDisposition.READY,
            ),
        )

    with pytest.raises(ValueError, match="连续"):
        validate_extraction_result(
            request,
            ExtractionResult(
                source_sha256=request.source.source_sha256,
                extractor_kind="W",
                extractor_version="fake-v1",
                pages=(
                    ExtractedPage(
                        logical_page=1,
                        page_number=None,
                        block_orders=(1, 0),
                    ),
                ),
                text_blocks=tuple(reversed(valid.text_blocks)),
                disposition=IngestionDisposition.READY,
            ),
        )


def test_failed_extraction_requires_structured_failure(tmp_path):
    request = ExtractionRequest.from_source_record(_record(tmp_path), run_id="run-123")

    with pytest.raises(ValueError, match="failure"):
        ExtractionResult(
            source_sha256=request.source.source_sha256,
            extractor_kind="W",
            extractor_version="fake-v1",
            pages=(),
            text_blocks=(),
            disposition=IngestionDisposition.FAILED,
        )

    result = ExtractionResult(
        source_sha256=request.source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(),
        text_blocks=(),
        disposition=IngestionDisposition.FAILED,
        failure=ExtractionFailure(
            stage="extraction",
            code="tool_failed",
            message="转换工具失败",
            retryable=False,
        ),
    )
    validate_extraction_result(request, result)
