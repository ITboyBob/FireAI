from dataclasses import replace as dataclass_replace
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_ingestion_batch import (
    BatchFileResult,
    BatchReport,
    FileAttempt,
    FileState,
    ReviewRecord,
    StateEvent,
    apply_review,
    load_batch_report,
    save_batch_report,
    transition_file,
    write_quality_report_once,
)
from app.services.legal_quality_gates import (
    GateOutcome,
    GateResult,
    QualityReport,
)


def _quality_report() -> QualityReport:
    return QualityReport(
        ruleset_version="legal-quality-v1",
        source_sha256="a" * 64,
        document_id="doc_example",
        gates=(
            GateResult(
                gate_id="source_identity",
                outcome=GateOutcome.PASS,
            ),
        ),
        overall=GateOutcome.PASS,
    )


def _review_record(
    *,
    passed: bool = True,
    reviewer: str = "reviewer@example.com",
    reviewed_at: str = "2026-06-29T12:00:00Z",
    source_sha256: str = "a" * 64,
    evidence_refs: tuple[str, ...] = ("source_identity",),
) -> ReviewRecord:
    return ReviewRecord(
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        source_sha256=source_sha256,
        decision="review_passed" if passed else "review_rejected",
        evidence_refs=evidence_refs,
        notes="",
    )


def test_transition_discovered_to_processing():
    new_state, event = transition_file(
        current_state=FileState.DISCOVERED,
        event_type="start_processing",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.PROCESSING
    assert event.from_state == FileState.DISCOVERED
    assert event.to_state == FileState.PROCESSING


def test_transition_processing_to_auto_passed():
    new_state, event = transition_file(
        current_state=FileState.PROCESSING,
        event_type="quality_ready",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.AUTO_PASSED


def test_transition_processing_to_review_required():
    new_state, event = transition_file(
        current_state=FileState.PROCESSING,
        event_type="quality_review_required",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.REVIEW_REQUIRED


def test_transition_processing_to_failed():
    new_state, event = transition_file(
        current_state=FileState.PROCESSING,
        event_type="quality_failed",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.FAILED


def test_transition_review_required_to_processing():
    new_state, event = transition_file(
        current_state=FileState.REVIEW_REQUIRED,
        event_type="reprocess",
        source_sha256="a" * 64,
        attempt_id="attempt-2",
    )
    assert new_state == FileState.PROCESSING


def test_transition_review_required_to_review_passed():
    new_state, event = transition_file(
        current_state=FileState.REVIEW_REQUIRED,
        event_type="review_approved",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.REVIEW_PASSED


def test_transition_review_required_to_failed():
    new_state, event = transition_file(
        current_state=FileState.REVIEW_REQUIRED,
        event_type="quality_failed",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.FAILED


def test_transition_auto_passed_to_committing():
    new_state, event = transition_file(
        current_state=FileState.AUTO_PASSED,
        event_type="start_commit",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.COMMITTING


def test_transition_review_passed_to_committing():
    new_state, event = transition_file(
        current_state=FileState.REVIEW_PASSED,
        event_type="start_commit",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.COMMITTING


def test_transition_committing_to_committed():
    new_state, event = transition_file(
        current_state=FileState.COMMITTING,
        event_type="commit_succeeded",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.COMMITTED


def test_transition_committing_to_failed():
    new_state, event = transition_file(
        current_state=FileState.COMMITTING,
        event_type="commit_failed",
        source_sha256="a" * 64,
        attempt_id="attempt-1",
    )
    assert new_state == FileState.FAILED


def test_transition_failed_to_processing():
    new_state, event = transition_file(
        current_state=FileState.FAILED,
        event_type="retry",
        source_sha256="a" * 64,
        attempt_id="attempt-2",
    )
    assert new_state == FileState.PROCESSING


def test_committed_is_terminal():
    with pytest.raises(ValueError, match="terminal"):
        transition_file(
            current_state=FileState.COMMITTED,
            event_type="retry",
            source_sha256="a" * 64,
            attempt_id="attempt-2",
        )


def test_transition_rejects_digest_mismatch():
    with pytest.raises(ValueError, match="SHA-256"):
        transition_file(
            current_state=FileState.DISCOVERED,
            event_type="start_processing",
            source_sha256="invalid",
            attempt_id="attempt-1",
        )


def test_transition_rejects_illegal_transition():
    with pytest.raises(ValueError, match="discovered -> quality_ready"):
        transition_file(
            current_state=FileState.DISCOVERED,
            event_type="quality_ready",
            source_sha256="a" * 64,
            attempt_id="attempt-1",
        )


def test_apply_review_requires_full_evidence():
    record = _review_record(reviewer="")
    with pytest.raises(ValueError, match="reviewer"):
        apply_review(
            current_state=FileState.REVIEW_REQUIRED,
            review_record=record,
            quality_report=_quality_report(),
            attempt_id="attempt-1",
        )


def test_apply_review_rejects_when_quality_fails():
    report = dataclass_replace(_quality_report(), overall=GateOutcome.FAIL)
    record = _review_record()
    with pytest.raises(ValueError, match="quality"):
        apply_review(
            current_state=FileState.REVIEW_REQUIRED,
            review_record=record,
            quality_report=report,
            attempt_id="attempt-1",
        )


def test_apply_review_rejects_digest_mismatch():
    record = _review_record(source_sha256="b" * 64)
    with pytest.raises(ValueError, match="source_sha256"):
        apply_review(
            current_state=FileState.REVIEW_REQUIRED,
            review_record=record,
            quality_report=_quality_report(),
            attempt_id="attempt-1",
        )


def test_apply_review_allows_passed_when_quality_passes():
    record = _review_record()
    new_state, event = apply_review(
        current_state=FileState.REVIEW_REQUIRED,
        review_record=record,
        quality_report=_quality_report(),
        attempt_id="attempt-1",
    )
    assert new_state == FileState.REVIEW_PASSED


def test_apply_review_rejects_non_review_state():
    record = _review_record()
    with pytest.raises(ValueError, match="review_required"):
        apply_review(
            current_state=FileState.PROCESSING,
            review_record=record,
            quality_report=_quality_report(),
            attempt_id="attempt-1",
        )


def test_write_quality_report_once_creates_file(tmp_path: Path):
    report = _quality_report()
    attempt = FileAttempt(
        attempt_id="attempt-1",
        source_sha256=report.source_sha256,
        state=FileState.AUTO_PASSED,
    )
    path = tmp_path / "attempt-1.quality.json"
    written = write_quality_report_once(path, attempt, report)
    assert written is True
    assert path.exists()


def test_write_quality_report_once_refuses_overwrite(tmp_path: Path):
    report = _quality_report()
    attempt = FileAttempt(
        attempt_id="attempt-1",
        source_sha256=report.source_sha256,
        state=FileState.AUTO_PASSED,
    )
    path = tmp_path / "attempt-1.quality.json"
    path.write_text("{}")
    written = write_quality_report_once(path, attempt, report)
    assert written is False


def test_write_quality_report_once_rejects_digest_mismatch(tmp_path: Path):
    report = _quality_report()
    attempt = FileAttempt(
        attempt_id="attempt-1",
        source_sha256="b" * 64,
        state=FileState.AUTO_PASSED,
    )
    path = tmp_path / "attempt-1.quality.json"
    with pytest.raises(ValueError, match="source_sha256"):
        write_quality_report_once(path, attempt, report)


def test_write_quality_report_once_rejects_forbidden_keys(tmp_path: Path):
    report = _quality_report()
    attempt = FileAttempt(
        attempt_id="attempt-1",
        source_sha256=report.source_sha256,
        state=FileState.AUTO_PASSED,
        measured={"raw_text": "泄露正文"},
    )
    path = tmp_path / "attempt-1.quality.json"
    with pytest.raises(ValueError, match="raw_text"):
        write_quality_report_once(path, attempt, report)


def test_save_batch_report_round_trips(tmp_path: Path):
    report_path = tmp_path / "batch.json"
    quality_path = tmp_path / "attempt-1.quality.json"
    quality_path.write_text('{"overall": "pass"}')
    quality_digest = sha256(quality_path.read_bytes()).hexdigest()

    results = (
        BatchFileResult(
            relative_path="a/b.doc",
            source_sha256="a" * 64,
            document_id="doc_a",
            attempt_id="attempt-1",
            final_state=FileState.COMMITTED,
            quality_report_path=str(quality_path),
            quality_report_sha256=quality_digest,
        ),
    )
    report = save_batch_report(
        report_path,
        batch_id="batch-1",
        source_root=tmp_path / "sources",
        results=results,
    )
    assert report_path.exists()
    loaded = load_batch_report(report_path)
    assert loaded.batch_id == "batch-1"
    assert len(loaded.results) == 1
    assert loaded.results[0].document_id == "doc_a"


def test_batch_report_summary_counts():
    results = (
        BatchFileResult(
            relative_path="a.doc",
            source_sha256="a" * 64,
            document_id="doc_a",
            attempt_id="attempt-1",
            final_state=FileState.COMMITTED,
        ),
        BatchFileResult(
            relative_path="b.doc",
            source_sha256="b" * 64,
            document_id="doc_b",
            attempt_id="attempt-1",
            final_state=FileState.REVIEW_REQUIRED,
        ),
        BatchFileResult(
            relative_path="c.doc",
            source_sha256="c" * 64,
            document_id="doc_c",
            attempt_id="attempt-1",
            final_state=FileState.FAILED,
        ),
    )
    report = BatchReport(
        batch_id="batch-1",
        source_root=Path("/tmp"),
        results=results,
    )
    assert report.summary["committed"] == 1
    assert report.summary["review_required"] == 1
    assert report.summary["failed"] == 1
    assert report.overall_status == "completed_with_exceptions"
