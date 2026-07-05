from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.eval_ws_rag.dataset_models import EvaluationDataset
from scripts.eval_ws_rag.dataset_store import load_dataset
from scripts.eval_ws_rag.report_models import ErrorReport, EvaluationReport

LOGGER = logging.getLogger(__name__)


def load_run(run_dir: Path) -> tuple[EvaluationReport, ErrorReport]:
    """Load and validate the paired report.json and errors.json from a run directory."""
    if not run_dir.exists():
        raise ValueError(f"run directory not found: {run_dir}")
    report_path = run_dir / "report.json"
    errors_path = run_dir / "errors.json"
    if not report_path.exists():
        raise ValueError(f"report.json not found in {run_dir}")
    if not errors_path.exists():
        raise ValueError(f"errors.json not found in {run_dir}")

    report = EvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    errors = ErrorReport.model_validate_json(errors_path.read_text(encoding="utf-8"))

    if report.schema_version != errors.schema_version:
        raise ValueError("schema_version mismatch between report.json and errors.json")
    if report.run_id != errors.run_id:
        raise ValueError("run_id mismatch between report.json and errors.json")
    if report.created_at != errors.created_at:
        raise ValueError("created_at mismatch between report.json and errors.json")

    return report, errors


def _load_chunk_source_sha256(chunks_dir: Path, document_id: str) -> str:
    file_path = chunks_dir / f"{document_id}.jsonl"
    if not file_path.exists():
        raise ValueError(f"chunk file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {file_path}: {exc}") from exc
            source_sha256 = chunk.get("source_sha256")
            if source_sha256:
                return str(source_sha256)
    raise ValueError(f"no source_sha256 found in {file_path}")


def verify_run(
    *,
    dataset_path: Path,
    run_dir: Path,
    data_dir: Path = Path("data"),
) -> dict[str, Any]:
    """Verify a published run against its dataset and the corpus on disk.

    The verifier is read-only: it does not call models or mutate files.
    """
    dataset = load_dataset(dataset_path)
    report, errors = load_run(run_dir)

    failures: list[str] = []

    # Dataset identity must match exactly.
    if report.dataset.dataset_id != dataset.dataset_id:
        failures.append(
            f"dataset_id mismatch: report={report.dataset.dataset_id}, dataset={dataset.dataset_id}"
        )
    if report.dataset.dataset_fingerprint != dataset.dataset_fingerprint:
        failures.append(
            f"dataset_fingerprint mismatch: report={report.dataset.dataset_fingerprint}, "
            f"dataset={dataset.dataset_fingerprint}"
        )
    report_doc_ids = sorted(report.dataset.document_ids)
    dataset_doc_ids = sorted(doc.document_id for doc in dataset.documents)
    if report_doc_ids != dataset_doc_ids:
        failures.append(
            f"document_ids mismatch: report={report_doc_ids}, dataset={dataset_doc_ids}"
        )

    # Document/question counts must be internally consistent.
    total_questions = sum(doc.question_count for doc in report.documents)
    if report.summary.question_count != total_questions:
        failures.append(
            f"summary.question_count ({report.summary.question_count}) != sum of document counts ({total_questions})"
        )
    for doc in report.documents:
        if len(doc.questions) != doc.question_count:
            failures.append(
                f"document {doc.document_id}: questions length ({len(doc.questions)}) != "
                f"question_count ({doc.question_count})"
            )

    # Corpus chunks must exist and match the source_sha256 recorded in the report.
    chunks_dir = data_dir / "chunks"
    for doc in report.documents:
        try:
            chunk_sha256 = _load_chunk_source_sha256(chunks_dir, doc.document_id)
        except ValueError as exc:
            failures.append(str(exc))
            continue
        if chunk_sha256 != doc.source_sha256:
            failures.append(
                f"document {doc.document_id}: source_sha256 mismatch between report ({doc.source_sha256}) "
                f"and chunks ({chunk_sha256})"
            )

    # Errors must reference questions that exist in the report, if provided.
    valid_question_ids = {
        q.question_id
        for doc in report.documents
        for q in doc.questions
    }
    valid_document_ids = {doc.document_id for doc in report.documents}
    for err in errors.errors:
        if err.question_id is not None and err.question_id not in valid_question_ids:
            failures.append(
                f"error references unknown question_id: {err.question_id}"
            )
        if err.document_id is not None and err.document_id not in valid_document_ids:
            failures.append(
                f"error references unknown document_id: {err.document_id}"
            )

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "dataset_id": dataset.dataset_id,
        "dataset_fingerprint": dataset.dataset_fingerprint,
        "run_id": report.run_id,
        "document_count": len(report.documents),
        "question_count": report.summary.question_count,
        "passed_questions": report.summary.passed_questions,
        "failed_questions_count": report.summary.failed_questions_count,
        "red_line_failures_count": report.summary.red_line_failures_count,
        "overall_pass_rate": report.summary.overall_pass_rate,
        "error_count": len(errors.errors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读核验已发布的 W-S RAG 评测 Run。"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="dataset.json 路径。",
    )
    parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="已发布 run 目录路径。",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="数据根目录，默认 data。",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        result = verify_run(
            dataset_path=args.dataset,
            run_dir=args.run,
            data_dir=args.data_dir,
        )
    except Exception as exc:
        LOGGER.error("核验失败: %s", exc)
        return 1

    LOGGER.info("核验通过")
    LOGGER.info("dataset_id: %s", result["dataset_id"])
    LOGGER.info("dataset_fingerprint: %s", result["dataset_fingerprint"])
    LOGGER.info("run_id: %s", result["run_id"])
    LOGGER.info("文档数: %s", result["document_count"])
    LOGGER.info("问题数: %s", result["question_count"])
    LOGGER.info("通过: %s, 失败: %s, 红线: %s",
                result["passed_questions"],
                result["failed_questions_count"],
                result["red_line_failures_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
