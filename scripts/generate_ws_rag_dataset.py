from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.eval_ws_rag.dataset_models import DatasetDocument, EvaluationDataset
from scripts.eval_ws_rag.dataset_store import save_dataset_atomic
from scripts.eval_ws_rag.document_loader import DocumentLoadError, load_document_chunks
from scripts.eval_ws_rag.question_generator import (
    QuestionGenerationError,
    build_question_generator_client,
    generate_document_questions,
)

LOGGER = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"environment variable {name} must be an integer") from exc


def _build_question_counts(args: argparse.Namespace) -> dict[str, int]:
    return {
        "frequent": args.frequent if args.frequent is not None else _int_env(
            "WS_RAG_FREQUENT_QUESTIONS_PER_DOCUMENT", 1
        ),
        "boundary": args.boundary if args.boundary is not None else _int_env(
            "WS_RAG_BOUNDARY_QUESTIONS_PER_DOCUMENT", 1
        ),
        "diversity": args.diversity if args.diversity is not None else _int_env(
            "WS_RAG_DIVERSITY_QUESTIONS_PER_DOCUMENT", 1
        ),
    }


def _build_question_generator_client():
    """Thin wrapper so tests can monkeypatch CLI client construction."""
    return build_question_generator_client()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="为 W-S1/W-S2 Word 法规生成不可变评测问题集。"
    )
    parser.add_argument(
        "--document-id",
        action="append",
        required=True,
        help="目标文档 ID，可多次传入。",
    )
    parser.add_argument("--dataset-id", required=True, help="dataset 唯一标识。")
    parser.add_argument("--seed", type=int, required=True, help="问题生成随机种子。")
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("data/chunks"),
        help="chunks 目录，默认 data/chunks。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/eval/ws_rag_datasets"),
        help="dataset 输出根目录，默认 data/eval/ws_rag_datasets。",
    )
    parser.add_argument(
        "--frequent", type=int, default=None, help="每份文档高频问题数量。"
    )
    parser.add_argument(
        "--boundary", type=int, default=None, help="每份文档边界问题数量。"
    )
    parser.add_argument(
        "--diversity", type=int, default=None, help="每份文档多样性问题数量。"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    counts = _build_question_counts(args)
    if all(c <= 0 for c in counts.values()):
        LOGGER.error("至少一类问题数量大于 0")
        return 1

    try:
        client = _build_question_generator_client()
    except Exception as exc:
        LOGGER.error("构建问题生成客户端失败: %s", exc)
        return 1

    documents: list[DatasetDocument] = []
    for document_id in args.document_id:
        try:
            loaded = load_document_chunks(args.chunks_dir, document_id)
        except DocumentLoadError as exc:
            LOGGER.error("加载文档 %s 失败: %s", document_id, exc)
            return 1

        try:
            questions = generate_document_questions(
                client=client,
                chunks=loaded.chunks,
                document_id=document_id,
                counts=counts,
                seed=args.seed,
            )
        except QuestionGenerationError as exc:
            LOGGER.error("生成问题失败: %s", exc)
            return 1

        if not questions:
            LOGGER.error("文档 %s 未生成任何问题", document_id)
            return 1

        documents.append(
            DatasetDocument(
                document_id=document_id,
                title=loaded.title,
                source_sha256=loaded.source_sha256,
                content_class=loaded.content_class,
                source_summary=f"{loaded.extraction_class}-{loaded.content_class} {loaded.title}",
                questions=questions,
            )
        )

    dataset = EvaluationDataset(
        schema_version="1.0.0",
        dataset_id=args.dataset_id,
        dataset_fingerprint="placeholder",
        created_at=datetime.now(timezone.utc),
        generator_model=client.model,
        generator_prompt_version=client.prompt_version,
        generation_seed=args.seed,
        documents=documents,
    )

    try:
        dataset_path = save_dataset_atomic(dataset, args.output_dir)
    except FileExistsError as exc:
        LOGGER.error("dataset 已存在，禁止覆盖: %s", exc)
        return 1
    except Exception as exc:
        LOGGER.error("保存 dataset 失败: %s", exc)
        return 1

    LOGGER.info("dataset 已生成: %s", dataset_path)
    LOGGER.info("dataset_id: %s", dataset.dataset_id)
    LOGGER.info("dataset_fingerprint: %s", dataset.dataset_fingerprint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
