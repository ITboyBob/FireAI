from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.eval_ws_rag.report_models import EvaluationReport


REGISTRY_SCHEMA_VERSION = "1.0.0"


class BaselineError(RuntimeError):
    """Raised when a baseline operation cannot be completed safely."""


class IncomparableRunsError(BaselineError):
    """Raised when two runs do not share the same measurement口径."""


def _schema_major(version: str) -> int:
    return int(version.split(".")[0])


def _load_report(run_dir: Path) -> EvaluationReport:
    if not run_dir.exists():
        raise BaselineError(f"run directory not found: {run_dir}")
    report_path = run_dir / "report.json"
    if not report_path.exists():
        raise BaselineError(f"report.json not found in {run_dir}")
    text = report_path.read_text(encoding="utf-8")
    return EvaluationReport.model_validate_json(text)


def _load_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "baselines": {}}
    text = registry_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BaselineError(f"registry file is corrupt: {registry_path}") from exc
    if not isinstance(data, dict) or "baselines" not in data:
        raise BaselineError(f"registry file is corrupt: {registry_path}")
    return data


def _save_registry_atomic(registry_path: Path, data: dict[str, Any]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=registry_path.name + ".",
        dir=str(registry_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        tmp_path_obj = Path(tmp_path)
        tmp_path_obj.replace(registry_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def register_baseline(
    *,
    name: str,
    run_dir: Path,
    registry_path: Path,
    replace: bool = False,
) -> dict[str, Any]:
    """Register an immutable run as a named baseline.

    By default the same baseline name cannot be overwritten. With ``replace=True``
    the previous run path is retained as ``previous_run_path`` for audit.
    """
    report = _load_report(run_dir)
    data = _load_registry(registry_path)
    baselines = data.setdefault("baselines", {})

    previous_run_path: str | None = None
    if name in baselines:
        if not replace:
            raise FileExistsError(f"baseline {name!r} already exists")
        previous_run_path = baselines[name].get("run_path")

    entry = {
        "run_path": str(run_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": report.dataset.dataset_id,
        "dataset_fingerprint": report.dataset.dataset_fingerprint,
        "protocol_fingerprint": report.protocol.protocol_fingerprint,
        "previous_run_path": previous_run_path,
    }
    baselines[name] = entry
    _save_registry_atomic(registry_path, data)
    return entry


def load_baseline(*, name: str, registry_path: Path) -> dict[str, Any]:
    """Load a baseline entry by name."""
    data = _load_registry(registry_path)
    baselines = data.get("baselines", {})
    if name not in baselines:
        raise BaselineError(f"baseline {name!r} not found")
    return baselines[name]


def _collect_question_metrics(report: EvaluationReport) -> dict[str, dict[str, float]]:
    """Map question_id -> metric dict for a report."""
    result: dict[str, dict[str, float]] = {}
    for doc in report.documents:
        for q in doc.questions:
            metrics = {k: float(v) for k, v in q.metrics.as_dict().items()}
            result[q.question_id] = metrics
    return result


def _system_diff(
    baseline: EvaluationReport,
    current: EvaluationReport,
) -> list[dict[str, Any]]:
    """Return human-readable system-level differences."""
    fields = [
        ("git_commit", baseline.system.git_commit, current.system.git_commit),
        ("git_dirty", baseline.system.git_dirty, current.system.git_dirty),
        ("corpus_fingerprint", baseline.system.corpus_fingerprint, current.system.corpus_fingerprint),
        ("answer_model", baseline.protocol.answer_model, current.protocol.answer_model),
        ("judge_model", baseline.protocol.judge_model, current.protocol.judge_model),
    ]
    return [
        {"field": name, "baseline": b, "current": c}
        for name, b, c in fields
        if b != c
    ]


def compare_runs(
    *,
    baseline_run_dir: Path,
    current_run_dir: Path,
    eps: float = 1e-9,
) -> dict[str, Any]:
    """Compare two runs that share the same dataset and protocol.

    Returns a dict with metric deltas, win/tie/loss counts and system diff.
    Raises ``IncomparableRunsError`` when the runs do not share the same口径.
    """
    baseline = _load_report(baseline_run_dir)
    current = _load_report(current_run_dir)

    reasons: list[str] = []
    if _schema_major(baseline.schema_version) != _schema_major(current.schema_version):
        reasons.append("schema major version differs")
    if baseline.dataset.dataset_id != current.dataset.dataset_id:
        reasons.append("dataset_id differs")
    if baseline.dataset.dataset_fingerprint != current.dataset.dataset_fingerprint:
        reasons.append("dataset_fingerprint differs")
    if baseline.protocol.protocol_fingerprint != current.protocol.protocol_fingerprint:
        reasons.append("protocol_fingerprint differs")

    baseline_doc_ids = sorted(baseline.dataset.document_ids)
    current_doc_ids = sorted(current.dataset.document_ids)
    if baseline_doc_ids != current_doc_ids:
        reasons.append("document_ids differ")

    baseline_questions = _collect_question_metrics(baseline)
    current_questions = _collect_question_metrics(current)
    baseline_qids = set(baseline_questions)
    current_qids = set(current_questions)
    if baseline_qids != current_qids:
        reasons.append("question_ids differ")

    if reasons:
        return {
            "comparable": False,
            "baseline_run_id": baseline.run_id,
            "current_run_id": current.run_id,
            "reasons": reasons,
        }

    metric_names = [
        "context_relevancy",
        "source_coverage",
        "faithfulness",
        "answer_relevance",
        "citation_validity",
        "refusal_appropriateness",
    ]

    per_question: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, int]] = {
        name: {"wins": 0, "ties": 0, "losses": 0}
        for name in metric_names
    }
    total_wins = 0
    total_ties = 0
    total_losses = 0

    for qid in sorted(baseline_qids):
        base_metrics = baseline_questions[qid]
        cur_metrics = current_questions[qid]
        deltas: dict[str, float] = {}
        question_wins = 0
        question_losses = 0
        for name in metric_names:
            delta = cur_metrics[name] - base_metrics[name]
            deltas[name] = delta
            if delta > eps:
                aggregate[name]["wins"] += 1
                question_wins += 1
            elif delta < -eps:
                aggregate[name]["losses"] += 1
                question_losses += 1
            else:
                aggregate[name]["ties"] += 1

        if question_wins > question_losses:
            total_wins += 1
        elif question_losses > question_wins:
            total_losses += 1
        else:
            total_ties += 1

        per_question.append(
            {
                "question_id": qid,
                "deltas": deltas,
                "outcome": (
                    "win" if question_wins > question_losses
                    else "loss" if question_losses > question_wins
                    else "tie"
                ),
            }
        )

    total_compared = total_wins + total_ties + total_losses
    win_rate = total_wins / total_compared if total_compared else 0.0

    return {
        "comparable": True,
        "baseline_run_id": baseline.run_id,
        "current_run_id": current.run_id,
        "total_questions_compared": total_compared,
        "win_rate": win_rate,
        "overall": {"wins": total_wins, "ties": total_ties, "losses": total_losses},
        "per_metric": aggregate,
        "per_question": per_question,
        "system_diff": _system_diff(baseline, current),
        "baseline_overall_pass_rate": baseline.summary.overall_pass_rate,
        "current_overall_pass_rate": current.summary.overall_pass_rate,
    }
