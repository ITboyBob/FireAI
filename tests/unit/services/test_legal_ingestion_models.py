from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ContentSignals,
    ExtractionClass,
    FrozenBatchInput,
    IngestionDisposition,
    IngestionInput,
    LegalSourceClassification,
    LegalSourceRecord,
    SourceProbe,
    SourceRef,
)


SOURCE_DIGEST = "a" * 64
BATCH_DIGEST = "b" * 64


def _source_ref(tmp_path: Path) -> SourceRef:
    source_path = tmp_path / "nested" / "sample.docx"
    source_path.parent.mkdir()
    source_path.write_bytes(b"sample")
    return SourceRef(
        relative_path="nested/sample.docx",
        source_path=source_path,
        source_sha256=SOURCE_DIGEST,
        size_bytes=6,
        declared_extension=".docx",
    )


def _evidence() -> ClassificationEvidence:
    return ClassificationEvidence(
        source_sha256=SOURCE_DIGEST,
        signature_kind="wordprocessingml",
        detected_mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        declared_extension=".docx",
        conversion_succeeded=True,
        converted_character_count=120,
    )


def test_classification_and_ingestion_enums_have_stable_values():
    assert [item.value for item in ExtractionClass] == ["W", "PT", "PS", "PX"]
    assert [item.value for item in ContentClass] == ["S1", "S2", "S3", "S4"]
    assert [item.value for item in ClassificationDisposition] == [
        "ready",
        "review_required",
        "failed",
    ]
    assert [item.value for item in IngestionDisposition] == [
        "ready",
        "unsupported",
        "review_required",
        "failed",
    ]
    assert IngestionDisposition.READY.may_carry_commit_qualification is True
    assert all(
        item.may_carry_commit_qualification is False
        for item in (
            IngestionDisposition.UNSUPPORTED,
            IngestionDisposition.REVIEW_REQUIRED,
            IngestionDisposition.FAILED,
        )
    )


def test_source_ref_is_immutable_and_rejects_unsafe_relative_paths(tmp_path):
    source = _source_ref(tmp_path)

    with pytest.raises(FrozenInstanceError):
        source.size_bytes = 7  # type: ignore[misc]

    with pytest.raises(ValueError, match="相对路径"):
        SourceRef(
            relative_path="../sample.docx",
            source_path=source.source_path,
            source_sha256=SOURCE_DIGEST,
            size_bytes=6,
            declared_extension=".docx",
        )


def test_ingestion_input_requires_exactly_one_input_mode(tmp_path):
    source = _source_ref(tmp_path)
    batch = FrozenBatchInput(
        root=tmp_path.resolve(),
        sources=(source,),
        batch_digest=BATCH_DIGEST,
    )

    assert IngestionInput(single_source=source).single_source is source
    assert IngestionInput(batch=batch).batch is batch

    with pytest.raises(ValueError, match="恰好选择一种"):
        IngestionInput()
    with pytest.raises(ValueError, match="恰好选择一种"):
        IngestionInput(single_source=source, batch=batch)


def test_classification_rejects_ready_px_and_unclassified_extracted_content():
    evidence = _evidence()

    with pytest.raises(ValueError, match="PX"):
        LegalSourceClassification(
            extraction_class=ExtractionClass.PX,
            content_class=None,
            disposition=ClassificationDisposition.READY,
            evidence=evidence,
        )

    with pytest.raises(ValueError, match="内容分类"):
        LegalSourceClassification(
            extraction_class=ExtractionClass.W,
            content_class=None,
            disposition=ClassificationDisposition.READY,
            evidence=evidence,
            content_signals=ContentSignals(
                candidate_extracted=True,
                title_count=1,
                article_marker_count=10,
            ),
        )


def test_legal_source_record_binds_probe_and_classification_to_source_digest(tmp_path):
    source = _source_ref(tmp_path)
    probe = SourceProbe(
        source_sha256=SOURCE_DIGEST,
        signature_kind="wordprocessingml",
        detected_mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        declared_extension=".docx",
        readable=True,
    )
    classification = LegalSourceClassification(
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
        disposition=ClassificationDisposition.READY,
        evidence=_evidence(),
        content_signals=ContentSignals(
            candidate_extracted=True,
            title_count=1,
            article_marker_count=10,
        ),
    )

    record = LegalSourceRecord(
        source=source,
        probe=probe,
        classification=classification,
    )

    assert record.extraction_class is ExtractionClass.W
    assert record.content_class is ContentClass.S1

    with pytest.raises(ValueError, match="摘要"):
        LegalSourceRecord(
            source=source,
            probe=SourceProbe(
                source_sha256="c" * 64,
                signature_kind="wordprocessingml",
                detected_mime_type="application/zip",
                declared_extension=".docx",
                readable=True,
            ),
            classification=classification,
        )
