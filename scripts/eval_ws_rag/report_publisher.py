from __future__ import annotations

import fcntl
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from scripts.eval_ws_rag.report_models import ErrorReport, EvaluationReport


class FileLock:
    """Simple advisory file lock using flock."""

    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None
        self._local_lock = threading.Lock()

    def __enter__(self):
        self._local_lock.acquire()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._fd is not None:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
                self._fd = None
        finally:
            self._local_lock.release()


def _validate_unique_question_ids(report: EvaluationReport) -> None:
    """数据契约第 10 条：每个 question_id 在报告内跨文档唯一，重号即拒绝发布。"""
    seen: set[str] = set()
    for document in report.documents:
        for question in document.questions:
            if question.question_id in seen:
                raise ValueError(
                    f"question_id {question.question_id} 跨文档重复，拒绝发布"
                )
            seen.add(question.question_id)


def publish_run_atomic(
    report: EvaluationReport,
    errors: ErrorReport,
    reports_root: Path,
    lock_factory: Any | None = None,
) -> Path:
    """Atomically publish a run directory containing report.json and errors.json."""
    reports_root.mkdir(parents=True, exist_ok=True)
    run_id = report.run_id
    final_dir = reports_root / run_id

    if final_dir.exists():
        raise FileExistsError(f"run already exists: {final_dir}")

    lock_path = reports_root / ".publish.lock"
    lock = lock_factory(lock_path) if lock_factory else FileLock(lock_path)

    staging_dir = reports_root / f".{run_id}.tmp-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=False, exist_ok=False)

    try:
        with lock:
            if final_dir.exists():
                raise FileExistsError(f"run already exists: {final_dir}")

            _atomic_write_json(report.model_dump_json(indent=2), staging_dir / "report.json")
            _atomic_write_json(errors.model_dump_json(indent=2), staging_dir / "errors.json")

            report_text = (staging_dir / "report.json").read_text(encoding="utf-8")
            errors_text = (staging_dir / "errors.json").read_text(encoding="utf-8")
            reloaded_report = EvaluationReport.model_validate_json(report_text)
            reloaded_errors = ErrorReport.model_validate_json(errors_text)
            if reloaded_report.schema_version != reloaded_errors.schema_version:
                raise ValueError("schema_version mismatch between report.json and errors.json")
            if reloaded_report.run_id != reloaded_errors.run_id:
                raise ValueError("run_id mismatch between report.json and errors.json")
            if reloaded_report.created_at != reloaded_errors.created_at:
                raise ValueError("created_at mismatch between report.json and errors.json")
            _validate_unique_question_ids(reloaded_report)

            staging_dir.rename(final_dir)
            _fsync_path(reports_root)
    except Exception:
        _rm_tree(staging_dir)
        raise

    return final_dir


def _atomic_write_json(text: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.rename(target)
    _fsync_path(target.parent)


def _fsync_path(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            _rm_tree(item)
        else:
            item.unlink()
    path.rmdir()
