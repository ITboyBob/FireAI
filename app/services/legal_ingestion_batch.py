from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
import json
import re
import tempfile
from typing import Any, Literal

from app.services.legal_quality_gates import GateOutcome, QualityReport


class FileState(str, Enum):
    DISCOVERED = "discovered"
    PROCESSING = "processing"
    AUTO_PASSED = "auto_passed"
    REVIEW_REQUIRED = "review_required"
    REVIEW_PASSED = "review_passed"
    COMMITTING = "committing"
    COMMITTED = "committed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class StateEvent:
    event_type: str
    from_state: FileState
    to_state: FileState
    source_sha256: str
    attempt_id: str
    timestamp_utc: str
    reason_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewRecord:
    reviewer: str
    reviewed_at: str
    source_sha256: str
    decision: Literal["review_passed", "review_rejected"]
    evidence_refs: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class FileAttempt:
    attempt_id: str
    source_sha256: str
    state: FileState
    events: tuple[StateEvent, ...] = field(default_factory=tuple)
    quality_report_path: str | None = None
    quality_report_sha256: str | None = None
    review_record: ReviewRecord | None = None
    measured: dict[str, object] = field(default_factory=dict)

    def replace(self, **kwargs) -> "FileAttempt":
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        data.update(kwargs)
        return self.__class__(**data)


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchFileResult:
    relative_path: str
    source_sha256: str
    document_id: str
    attempt_id: str
    final_state: FileState
    quality_report_path: str | None = None
    quality_report_sha256: str | None = None
    reason_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchReport:
    batch_id: str
    source_root: Path
    results: tuple[BatchFileResult, ...]
    created_at: str = field(default_factory=lambda: _utc_now())

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "discovered": 0,
            "processing": 0,
            "auto_passed": 0,
            "review_required": 0,
            "review_passed": 0,
            "committing": 0,
            "committed": 0,
            "failed": 0,
        }
        for result in self.results:
            counts[result.final_state.value] = counts.get(result.final_state.value, 0) + 1
        return counts

    @property
    def overall_status(self) -> Literal["completed", "completed_with_exceptions"]:
        if any(
            result.final_state in {FileState.REVIEW_REQUIRED, FileState.FAILED}
            for result in self.results
        ):
            return "completed_with_exceptions"
        return "completed"


_STATE_TRANSITIONS: dict[tuple[FileState, str], FileState] = {
    (FileState.DISCOVERED, "start_processing"): FileState.PROCESSING,
    (FileState.PROCESSING, "quality_ready"): FileState.AUTO_PASSED,
    (FileState.PROCESSING, "quality_review_required"): FileState.REVIEW_REQUIRED,
    (FileState.PROCESSING, "quality_failed"): FileState.FAILED,
    (FileState.REVIEW_REQUIRED, "reprocess"): FileState.PROCESSING,
    (FileState.REVIEW_REQUIRED, "review_approved"): FileState.REVIEW_PASSED,
    (FileState.REVIEW_REQUIRED, "review_rejected"): FileState.FAILED,
    (FileState.REVIEW_REQUIRED, "quality_failed"): FileState.FAILED,
    (FileState.AUTO_PASSED, "start_commit"): FileState.COMMITTING,
    (FileState.REVIEW_PASSED, "start_commit"): FileState.COMMITTING,
    (FileState.COMMITTING, "commit_succeeded"): FileState.COMMITTED,
    (FileState.COMMITTING, "commit_failed"): FileState.FAILED,
    (FileState.FAILED, "retry"): FileState.PROCESSING,
}

_FORBIDDEN_QUALITY_KEYS = frozenset(
    {"raw_text", "full_text", "source_text", "attachment", "template"}
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def transition_file(
    *,
    current_state: FileState,
    event_type: str,
    source_sha256: str,
    attempt_id: str,
    reason_code: str | None = None,
) -> tuple[FileState, StateEvent]:
    _validate_sha256(source_sha256)
    if current_state is FileState.COMMITTED:
        raise ValueError(f"{current_state.value} is terminal")

    key = (current_state, event_type)
    if key not in _STATE_TRANSITIONS:
        raise ValueError(
            f"illegal transition: {current_state.value} -> {event_type}"
        )

    new_state = _STATE_TRANSITIONS[key]
    event = StateEvent(
        event_type=event_type,
        from_state=current_state,
        to_state=new_state,
        source_sha256=source_sha256,
        attempt_id=attempt_id,
        timestamp_utc=_utc_now(),
        reason_code=reason_code,
    )
    return new_state, event


def apply_review(
    *,
    current_state: FileState,
    review_record: ReviewRecord,
    quality_report: QualityReport,
    attempt_id: str,
) -> tuple[FileState, StateEvent]:
    if current_state is not FileState.REVIEW_REQUIRED:
        raise ValueError(
            f"review can only be applied in {FileState.REVIEW_REQUIRED.value}, "
            f"got {current_state.value}"
        )

    if not review_record.reviewer:
        raise ValueError("reviewer must be non-empty")
    if not review_record.reviewed_at:
        raise ValueError("reviewed_at must be non-empty")
    if not review_record.evidence_refs:
        raise ValueError("evidence_refs must not be empty")
    if review_record.source_sha256 != quality_report.source_sha256:
        raise ValueError("review source_sha256 does not match quality report")

    if quality_report.overall is GateOutcome.FAIL:
        raise ValueError("quality report has failing gates; review cannot override")

    if review_record.decision == "review_rejected":
        new_state = FileState.FAILED
        event_type = "review_rejected"
    else:
        new_state = FileState.REVIEW_PASSED
        event_type = "review_approved"

    event = StateEvent(
        event_type=event_type,
        from_state=current_state,
        to_state=new_state,
        source_sha256=quality_report.source_sha256,
        attempt_id=attempt_id,
        timestamp_utc=_utc_now(),
        reason_code="manual_review",
    )
    return new_state, event


def write_quality_report_once(
    path: Path,
    attempt: FileAttempt,
    quality_report: QualityReport,
) -> bool:
    _validate_sha256(attempt.source_sha256)
    if attempt.source_sha256 != quality_report.source_sha256:
        raise ValueError("attempt source_sha256 does not match quality report")

    _check_forbidden_keys(attempt.measured)
    _check_forbidden_keys(asdict(quality_report))

    if path.exists():
        return False

    payload = _serialize_quality_report(path, attempt, quality_report)
    _atomic_write_json(path, payload)
    return True


def save_batch_report(
    path: Path,
    *,
    batch_id: str,
    source_root: Path,
    results: tuple[BatchFileResult, ...],
) -> BatchReport:
    report = BatchReport(
        batch_id=batch_id,
        source_root=source_root,
        results=results,
    )
    payload = _batch_report_to_json(report)
    _atomic_write_json(path, payload)
    return report


def load_batch_report(path: Path) -> BatchReport:
    data = json.loads(path.read_text(encoding="utf-8"))
    results = tuple(
        BatchFileResult(
            relative_path=item["relative_path"],
            source_sha256=item["source_sha256"],
            document_id=item["document_id"],
            attempt_id=item["attempt_id"],
            final_state=FileState(item["final_state"]),
            quality_report_path=item.get("quality_report_path"),
            quality_report_sha256=item.get("quality_report_sha256"),
            reason_code=item.get("reason_code"),
        )
        for item in data["results"]
    )
    return BatchReport(
        batch_id=data["batch_id"],
        source_root=Path(data["source_root"]),
        results=results,
        created_at=data["created_at"],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_sha256(value: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"source_sha256 must be a lowercase SHA-256 hex string: {value!r}")


def _check_forbidden_keys(obj: Any) -> None:
    if isinstance(obj, dict):
        for key in obj:
            if key in _FORBIDDEN_QUALITY_KEYS:
                raise ValueError(f"quality report contains forbidden key: {key}")
            _check_forbidden_keys(obj[key])
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _check_forbidden_keys(item)


def _serialize_quality_report(
    path: Path,
    attempt: FileAttempt,
    quality_report: QualityReport,
) -> dict[str, Any]:
    gates = tuple(
        {
            "gate_id": gate.gate_id,
            "outcome": gate.outcome.value,
            "measured": gate.measured,
            "evidence_refs": gate.evidence_refs,
            "reason_code": gate.reason_code,
        }
        for gate in quality_report.gates
    )
    return {
        "ruleset_version": quality_report.ruleset_version,
        "source_sha256": quality_report.source_sha256,
        "document_id": quality_report.document_id,
        "overall": quality_report.overall.value,
        "gates": gates,
        "attempt_id": attempt.attempt_id,
        "attempt_state": attempt.state.value,
        "quality_report_sha256": _sha256_of_quality_json(
            quality_report.ruleset_version,
            quality_report.source_sha256,
            quality_report.document_id,
            quality_report.overall.value,
            gates,
        ),
        "written_at": _utc_now(),
    }


def _sha256_of_quality_json(
    ruleset_version: str,
    source_sha256: str,
    document_id: str,
    overall: str,
    gates: tuple[dict[str, Any], ...],
) -> str:
    payload = {
        "ruleset_version": ruleset_version,
        "source_sha256": source_sha256,
        "document_id": document_id,
        "overall": overall,
        "gates": gates,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _batch_report_to_json(report: BatchReport) -> dict[str, Any]:
    return {
        "batch_id": report.batch_id,
        "source_root": str(report.source_root),
        "results": [
            {
                "relative_path": result.relative_path,
                "source_sha256": result.source_sha256,
                "document_id": result.document_id,
                "attempt_id": result.attempt_id,
                "final_state": result.final_state.value,
                "quality_report_path": result.quality_report_path,
                "quality_report_sha256": result.quality_report_sha256,
                "reason_code": result.reason_code,
            }
            for result in report.results
        ],
        "summary": report.summary,
        "overall_status": report.overall_status,
        "created_at": report.created_at,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(serialized)
        temp_path = Path(handle.name)
    try:
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
