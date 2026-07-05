from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from scripts.eval_ws_rag.report_models import ErrorReport, EvaluationReport, utc_now


class DashboardRunError(ValueError):
    """Raised when the Dashboard cannot build a snapshot atomically."""


@dataclass(frozen=True, slots=True)
class RunRecord:
    """A complete and validated evaluation Run."""

    run_id: str
    created_at: datetime
    report: EvaluationReport
    errors: ErrorReport
    directory: Path


@dataclass(frozen=True, slots=True)
class InvalidRun:
    """A directory that looks like a Run but failed validation."""

    path: Path
    category: str
    reason: str


@dataclass
class RunCatalog:
    """Result of scanning the reports root for Runs."""

    valid_runs: list[RunRecord] = field(default_factory=list)
    invalid_runs: list[InvalidRun] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SingleRunView:
    """Read-only presentation model for a single Run."""

    run_id: str
    created_at: datetime
    report: EvaluationReport
    failure_code_counts: dict[str, int]
    error_stage_counts: dict[str, int]
    comparison_available: bool = False
    comparison_message: str = "当前只有一个 Run，暂无可比较对象"


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Immutable snapshot of discovered Runs and current selection."""

    root_dir: Path
    catalog: RunCatalog
    current_run: RunRecord | None
    single_run_view: SingleRunView | None
    loaded_at: datetime


def _is_supported_schema_version(version: Any) -> tuple[bool, str]:
    if not isinstance(version, str):
        return False, "schema_version 必须是字符串"
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return False, f"schema_version 必须是 semver: {version}"
    major = int(parts[0])
    if major != 1:
        return False, f"不支持的 schema 主版本: {major}"
    return True, ""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_cross_fields(report: EvaluationReport) -> None:
    """Validate consistency that the shared schema does not already enforce."""
    seen_question_ids: set[str] = set()

    for document in report.documents:
        actual_passed = sum(1 for question in document.questions if question.passed)
        actual_failed = len(document.questions) - actual_passed
        actual_red_lines = sum(
            len(question.red_line_failures) for question in document.questions
        )

        if document.passed_questions is not None and document.passed_questions != actual_passed:
            raise ValueError(
                f"文件 {document.document_id}: passed_questions "
                f"({document.passed_questions}) 与实际 ({actual_passed}) 不一致"
            )
        if (
            document.failed_questions_count is not None
            and document.failed_questions_count != actual_failed
        ):
            raise ValueError(
                f"文件 {document.document_id}: failed_questions_count "
                f"({document.failed_questions_count}) 与实际 ({actual_failed}) 不一致"
            )
        if (
            document.red_line_failures_count is not None
            and document.red_line_failures_count != actual_red_lines
        ):
            raise ValueError(
                f"文件 {document.document_id}: red_line_failures_count "
                f"({document.red_line_failures_count}) 与实际 ({actual_red_lines}) 不一致"
            )

        actual_failed_ids = {
            question.question_id for question in document.questions if not question.passed
        }
        if set(document.failed_questions or []) != actual_failed_ids:
            raise ValueError(
                f"文件 {document.document_id}: failed_questions 列表与实际失败问题不一致"
            )

        for question in document.questions:
            if question.question_id in seen_question_ids:
                raise ValueError(f"问题 ID 重复: {question.question_id}")
            seen_question_ids.add(question.question_id)

            chunk_ids = {chunk.chunk_id for chunk in question.retrieved_chunks}
            for citation in question.citations:
                if citation.matched_chunk_id not in chunk_ids:
                    raise ValueError(
                        f"问题 {question.question_id}: 引文 matched_chunk_id "
                        f"{citation.matched_chunk_id} 不在检索证据中"
                    )


def _inspect_run_directory(directory: Path, root_dir: Path) -> RunRecord | InvalidRun:
    """Validate a single candidate Run directory."""
    if directory.name.startswith("."):
        return InvalidRun(path=directory, category="ignored", reason="隐藏或暂存目录被忽略")

    try:
        directory.resolve().relative_to(root_dir.resolve())
    except ValueError:
        return InvalidRun(path=directory, category="validation_error", reason="路径逃逸出报告根目录")

    report_path = directory / "report.json"
    errors_path = directory / "errors.json"
    if not report_path.is_file() or not errors_path.is_file():
        return InvalidRun(
            path=directory,
            category="missing_file",
            reason="缺少 report.json 或 errors.json",
        )

    try:
        report_raw = _read_json(report_path)
        errors_raw = _read_json(errors_path)
    except Exception as exc:  # noqa: BLE001
        return InvalidRun(
            path=directory,
            category="json_error",
            reason=f"JSON 语法错误: {exc}",
        )

    report_version_ok, report_version_reason = _is_supported_schema_version(
        report_raw.get("schema_version")
    )
    errors_version_ok, errors_version_reason = _is_supported_schema_version(
        errors_raw.get("schema_version")
    )
    if not report_version_ok:
        return InvalidRun(
            path=directory,
            category="unsupported_schema",
            reason=report_version_reason,
        )
    if not errors_version_ok:
        return InvalidRun(
            path=directory,
            category="unsupported_schema",
            reason=errors_version_reason,
        )

    try:
        report = EvaluationReport.model_validate(report_raw)
        errors = ErrorReport.model_validate(errors_raw)
    except ValidationError as exc:
        for error in exc.errors():
            msg = str(error.get("msg", "")).lower()
            if "unsupported" in msg or "不支持的" in msg:
                return InvalidRun(
                    path=directory,
                    category="unsupported_schema",
                    reason=str(error.get("msg", msg)),
                )
        return InvalidRun(
            path=directory,
            category="validation_error",
            reason=str(exc),
        )

    if report.run_id != directory.name or errors.run_id != directory.name:
        return InvalidRun(
            path=directory,
            category="cross_file_inconsistent",
            reason="run_id 与目录名不一致",
        )
    if report.run_id != errors.run_id:
        return InvalidRun(
            path=directory,
            category="cross_file_inconsistent",
            reason="report.json 与 errors.json 的 run_id 不一致",
        )
    if report.schema_version != errors.schema_version:
        return InvalidRun(
            path=directory,
            category="cross_file_inconsistent",
            reason="report.json 与 errors.json 的 schema_version 不一致",
        )
    if report.created_at != errors.created_at:
        return InvalidRun(
            path=directory,
            category="cross_file_inconsistent",
            reason="report.json 与 errors.json 的 created_at 不一致",
        )

    try:
        _validate_cross_fields(report)
    except ValueError as exc:
        return InvalidRun(
            path=directory,
            category="cross_field_inconsistent",
            reason=str(exc),
        )

    return RunRecord(
        run_id=report.run_id,
        created_at=report.created_at,
        report=report,
        errors=errors,
        directory=directory,
    )


def discover_runs(root_dir: Path) -> RunCatalog:
    """Discover complete evaluation Runs under ``root_dir``.

    Staging directories (starting with ``.``), hidden directories, symlinks,
    and directories missing required files are ignored or reported as invalid.
    """
    catalog = RunCatalog()
    if not root_dir.exists():
        return catalog

    root_resolved = root_dir.resolve()
    for item in root_dir.iterdir():
        if not item.is_dir() or item.is_symlink():
            continue
        if item.name.startswith("."):
            continue
        result = _inspect_run_directory(item, root_resolved)
        if isinstance(result, RunRecord):
            catalog.valid_runs.append(result)
        else:
            catalog.invalid_runs.append(result)

    catalog.valid_runs.sort(key=lambda run: (run.created_at, run.directory.stat().st_mtime), reverse=True)
    return catalog


def build_single_run_view(run: RunRecord) -> SingleRunView:
    """Derive a read-only presentation view from a single Run.

    The view never re-computes ``passed`` or pass rates and never produces
    directional deltas, because only one Run is available in this phase.
    """
    failure_code_counts: Counter[str] = Counter()
    for document in run.report.documents:
        for question in document.questions:
            failure_code_counts.update(
                failure.code for failure in question.failure_reasons
            )

    error_stage_counts: Counter[str] = Counter(
        error.stage for error in run.errors.errors
    )

    return SingleRunView(
        run_id=run.run_id,
        created_at=run.created_at,
        report=run.report,
        failure_code_counts=dict(failure_code_counts),
        error_stage_counts=dict(error_stage_counts),
    )


def build_snapshot(
    root_dir: Path,
    current_run_id: str | None = None,
) -> DashboardSnapshot:
    """Build a fresh snapshot of all Runs and the current selection.

    If ``current_run_id`` still points to a valid Run, keep it; otherwise fall
    back to the latest valid Run. The whole snapshot is replaced atomically on
    success; callers should keep their old snapshot if this function raises.
    """
    catalog = discover_runs(root_dir)

    current_run: RunRecord | None = None
    if current_run_id:
        for run in catalog.valid_runs:
            if run.run_id == current_run_id:
                current_run = run
                break

    if current_run is None and catalog.valid_runs:
        current_run = catalog.valid_runs[0]

    single_run_view = (
        build_single_run_view(current_run) if current_run else None
    )

    return DashboardSnapshot(
        root_dir=root_dir,
        catalog=catalog,
        current_run=current_run,
        single_run_view=single_run_view,
        loaded_at=utc_now(),
    )
