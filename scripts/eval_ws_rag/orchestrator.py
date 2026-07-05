from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from app.core.settings import get_settings
from app.services.chat_client import OpenAIChatClient
from app.services.embedder import SentenceTransformerEmbedder
from app.services.retriever import Retriever
from scripts.eval_ws_rag.dataset_models import EvaluationDataset
from scripts.eval_ws_rag.dataset_store import load_dataset
from scripts.eval_ws_rag.eval_chat_client import StructuredEvalClient, build_judge_client
from scripts.eval_ws_rag.llm_judge import JudgeError, score_question as judge_score_question
from scripts.eval_ws_rag.rag_runner import RagStageError, run_question
from scripts.eval_ws_rag.report_aggregator import aggregate_document, aggregate_run
from scripts.eval_ws_rag.report_models import (
    DatasetIdentity,
    ErrorReport,
    EvaluationError,
    EvaluationProtocol,
    EvaluationReport,
    EvaluatedSystem,
    JudgeDetail as ReportJudgeDetail,
    JudgeResult as ReportJudgeResult,
    MetricScores,
    QuestionResult,
    compute_protocol_fingerprint,
)
from scripts.eval_ws_rag.report_publisher import publish_run_atomic
from scripts.eval_ws_rag.rule_validator import validate_rules

LOGGER = logging.getLogger(__name__)

RECOVERABLE_STAGES = {"answer_generation", "query_normalization"}
INDEX_FILE_NAMES = ["retrieval.db", "faiss.index", "vector_map.json"]


class FatalEvaluationError(Exception):
    """Fatal error that must abort the run before any formal publication."""

    def __init__(self, evaluation_error: EvaluationError):
        super().__init__(evaluation_error.message)
        self.evaluation_error = evaluation_error


@dataclass
class RunResult:
    run_dir: Path | None = None
    report: EvaluationReport | None = None
    errors: ErrorReport | None = None
    fatal_error: EvaluationError | None = None
    debug_path: Path | None = None


class RetrieverFactory(Protocol):
    def __call__(self, data_dir: Path) -> Retriever: ...


class AnswerClientFactory(Protocol):
    def __call__(self, answer_model: str) -> Any: ...


class JudgeClientFactory(Protocol):
    def __call__(self, judge_model: str) -> StructuredEvalClient: ...


class Publisher(Protocol):
    def __call__(self, report: EvaluationReport, errors: ErrorReport, reports_root: Path) -> Path: ...


def load_config(config_path: Path) -> dict[str, Any]:
    """Load evaluation runtime configuration from JSON."""
    text = config_path.read_text(encoding="utf-8")
    return json.loads(text)


def _git_info() -> tuple[str, bool]:
    """Return (commit_hex, dirty) for the current repository."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = "unknown"

    dirty = False
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(status)
    except Exception:
        dirty = True

    return commit, dirty


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_corpus_fingerprint(data_dir: Path, dataset: EvaluationDataset) -> str:
    """Return a stable fingerprint of the indexed corpus backing the dataset.

    The fingerprint covers the dataset's source identity (document ids,
    source_sha256, content class and source summary) plus the identity of the
    formal index files under ``data_dir/index``. Directory mtimes are never used.
    """
    documents = [
        {
            "document_id": doc.document_id,
            "source_sha256": doc.source_sha256,
            "content_class": doc.content_class,
            "source_summary": doc.source_summary,
        }
        for doc in sorted(dataset.documents, key=lambda d: d.document_id)
    ]

    index_dir = data_dir / "index"
    index_files: list[dict[str, Any]] = []
    if index_dir.exists():
        for f in sorted(index_dir.iterdir()):
            if f.is_file():
                index_files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "sha256": _sha256_file(f),
                    }
                )

    canonical = json.dumps(
        {"documents": documents, "index": index_files},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_protocol(config: dict[str, Any], *, judge_model: str, answer_model: str) -> EvaluationProtocol:
    thresholds = MetricScores(**config["thresholds"])
    judge_repetitions = int(config.get("default_judge_repetitions", 3))
    top_k = int(config.get("default_top_k", 5))
    return EvaluationProtocol(
        protocol_fingerprint=compute_protocol_fingerprint(
            judge_model=judge_model,
            judge_prompt_version="judge_v1",
            judge_repetitions=judge_repetitions,
            evidence_order_strategy="seed_shuffled",
            metric_algorithm_version="v1",
            thresholds=thresholds.as_dict(),
        ),
        judge_model=judge_model,
        judge_prompt_version="judge_v1",
        judge_repetitions=judge_repetitions,
        judge_calibrated=False,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
        answer_model=answer_model,
        answer_prompt_version="answer_v1",
        top_k=top_k,
    )


def _default_retriever_factory(data_dir: Path) -> Retriever:
    """加载真实检索器，必须带上本地 embedder 才能执行语义向量检索。"""
    index_dir = data_dir / "index"
    settings = get_settings()
    model_name = settings.embedding_model_name
    if not model_name:
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="向量嵌入模型未配置",
                error_type="ConfigurationError",
                message="环境变量 EMBEDDING_MODEL_NAME 未设置，无法执行向量检索",
                recoverable=False,
            )
        )

    embedder = SentenceTransformerEmbedder(
        model_name_or_path=model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_seq_length=settings.embedding_max_seq_length,
    )
    # 先 warm-up embedder 再加载 FAISS，避免首次 encode 时原生层崩溃。
    embedder.encode_queries(["warmup"])

    return Retriever.from_disk(
        keyword_db_path=index_dir / "retrieval.db",
        vector_index_path=index_dir / "faiss.index",
        vector_map_path=index_dir / "vector_map.json",
        embedder=embedder,
    )


def _default_answer_client_factory(answer_model: str) -> OpenAIChatClient:
    return OpenAIChatClient(
        api_key=os.environ.get("CHAT_API_KEY", ""),
        base_url=os.environ.get("CHAT_BASE_URL", ""),
        model=answer_model,
        timeout=float(os.environ.get("CHAT_TIMEOUT_SECONDS", "30")),
        temperature=0.0,
        max_retries=int(os.environ.get("WS_RAG_MODEL_MAX_RETRIES", "1")),
    )


def _default_judge_client_factory(judge_model: str) -> StructuredEvalClient:
    return build_judge_client(
        api_key=os.environ.get("WS_RAG_JUDGE_API_KEY", ""),
        base_url=os.environ.get("WS_RAG_JUDGE_BASE_URL", ""),
        model=judge_model,
        temperature=0.0,
        max_retries=int(os.environ.get("WS_RAG_MODEL_MAX_RETRIES", "1")),
    )


def _preflight(
    dataset_path: Path,
    data_dir: Path,
    reports_root: Path,
    run_id: str,
) -> tuple[EvaluationDataset, str, str]:
    """Run read-only preflight checks and return the loaded dataset plus model ids."""
    try:
        dataset = load_dataset(dataset_path)
    except FileNotFoundError as exc:
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="dataset 文件不存在",
                error_type=type(exc).__name__,
                message=str(exc),
                recoverable=False,
            )
        ) from exc
    except ValueError as exc:
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="dataset fingerprint 校验失败",
                error_type=type(exc).__name__,
                message=str(exc),
                recoverable=False,
            )
        ) from exc

    for document_id in [doc.document_id for doc in dataset.documents]:
        chunk_path = data_dir / "chunks" / f"{document_id}.jsonl"
        if not chunk_path.exists():
            raise FatalEvaluationError(
                EvaluationError(
                    stage="preflight",
                    stage_description="chunk 文件缺失",
                    error_type="FileNotFoundError",
                    message=f"chunk file not found: {chunk_path}",
                    recoverable=False,
                    input_snapshot={"document_id": document_id},
                )
            )

    index_dir = data_dir / "index"
    for name in INDEX_FILE_NAMES:
        if not (index_dir / name).exists():
            raise FatalEvaluationError(
                EvaluationError(
                    stage="preflight",
                    stage_description="索引文件缺失",
                    error_type="FileNotFoundError",
                    message=f"index file not found: {index_dir / name}",
                    recoverable=False,
                    input_snapshot={"missing_file": name},
                )
            )

    answer_model = os.environ.get("CHAT_MODEL", "").strip()
    judge_model = os.environ.get("WS_RAG_JUDGE_MODEL", "").strip()
    if not answer_model:
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="答案生成模型未配置",
                error_type="ConfigurationError",
                message="环境变量 CHAT_MODEL 未设置",
                recoverable=False,
            )
        )
    if not judge_model:
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="Judge 模型未配置",
                error_type="ConfigurationError",
                message="环境变量 WS_RAG_JUDGE_MODEL 未设置",
                recoverable=False,
            )
        )

    run_dir = reports_root / run_id
    if run_dir.exists():
        raise FatalEvaluationError(
            EvaluationError(
                stage="preflight",
                stage_description="run 目录已存在",
                error_type="FileExistsError",
                message=f"run already exists: {run_dir}",
                recoverable=False,
                input_snapshot={"run_id": run_id},
            )
        )

    return dataset, judge_model, answer_model


def _error_from_rag_stage(
    document_id: str,
    question_id: str,
    exc: RagStageError,
) -> EvaluationError:
    return EvaluationError(
        document_id=document_id,
        question_id=question_id,
        stage=exc.stage,
        stage_description=exc.stage_description,
        error_type=exc.error_type,
        message=exc.message,
        recoverable=exc.recoverable,
    )


def _judge_result_to_report(judge: Any) -> ReportJudgeResult:
    details = []
    for detail in judge.details:
        claims = None
        if detail.claims_verdict:
            claims = [{"verdict": v} for v in detail.claims_verdict]
        details.append(
            ReportJudgeDetail(
                repetition=detail.repetition,
                context_helpful=detail.context_helpful,
                claims_verdict=claims,
                answer_relevance_likert=detail.answer_relevance_likert,
            )
        )
    return ReportJudgeResult(
        context_relevancy=judge.context_relevancy,
        faithfulness=judge.faithfulness,
        answer_relevance=judge.answer_relevance,
        details=details,
        prompt_version=judge.prompt_version,
        model=judge.model,
    )


def run_evaluation(
    *,
    dataset_path: Path,
    run_id: str,
    data_dir: Path = Path("data"),
    reports_root: Path = Path("reports/ws_rag_eval"),
    config: dict[str, Any],
    retriever_factory: RetrieverFactory = _default_retriever_factory,
    answer_client_factory: AnswerClientFactory = _default_answer_client_factory,
    judge_client_factory: JudgeClientFactory = _default_judge_client_factory,
    publisher: Publisher = publish_run_atomic,
    _git_info_fn: Callable[[], tuple[str, bool]] = _git_info,
    _now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RunResult:
    """Run a full W-S RAG evaluation and atomically publish the result directory."""
    dataset, judge_model, answer_model = _preflight(dataset_path, data_dir, reports_root, run_id)

    protocol = _build_protocol(config, judge_model=judge_model, answer_model=answer_model)
    corpus_fingerprint = compute_corpus_fingerprint(data_dir, dataset)
    git_commit, git_dirty = _git_info_fn()
    system = EvaluatedSystem(
        git_commit=git_commit,
        git_dirty=git_dirty,
        corpus_fingerprint=corpus_fingerprint,
    )
    dataset_identity = DatasetIdentity(
        dataset_id=dataset.dataset_id,
        dataset_fingerprint=dataset.dataset_fingerprint,
        document_ids=sorted(doc.document_id for doc in dataset.documents),
    )

    created_at = _now_fn()
    retriever = retriever_factory(data_dir)
    answer_client = answer_client_factory(answer_model)
    judge_client = judge_client_factory(judge_model)

    max_retries = int(config.get("default_max_retries", 1))
    recoverable_errors = {"answer_generation"}

    document_scorecards: list[Any] = []
    errors: list[EvaluationError] = []

    for doc in dataset.documents:
        question_results: list[QuestionResult] = []
        for ds_question in doc.questions:
            try:
                rag_result = run_question(
                    retriever=retriever,
                    answer_client=answer_client,
                    question=ds_question.question,
                    document_id=doc.document_id,
                    top_k=protocol.top_k,
                    answer_model=answer_model,
                    max_retries=max_retries,
                    recoverable_errors=recoverable_errors,
                )
            except RagStageError as exc:
                err = _error_from_rag_stage(doc.document_id, ds_question.question_id, exc)
                # Answer-generation failures are treated as per-question recoverable errors
                # after the runner's internal retries are exhausted. Retrieval/fusion errors
                # remain fatal because they affect the whole corpus, not a single question.
                if exc.stage == "answer_generation":
                    err.recoverable = True
                    errors.append(err)
                    continue
                raise FatalEvaluationError(err) from exc

            try:
                judge = judge_score_question(
                    client=judge_client,
                    question=ds_question.question,
                    answer=rag_result.answer,
                    chunks=[c.model_dump(mode="json") for c in rag_result.retrieved_chunks],
                    repetitions=protocol.judge_repetitions,
                    seed=dataset.generation_seed,
                    question_id=ds_question.question_id,
                )
            except JudgeError as exc:
                err = EvaluationError(
                    document_id=doc.document_id,
                    question_id=ds_question.question_id,
                    stage="judge",
                    stage_description="Judge 打分失败",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    recoverable=False,
                    input_snapshot={"answer": rag_result.answer},
                )
                raise FatalEvaluationError(err) from exc

            validation = validate_rules(
                retrieved_chunks=rag_result.retrieved_chunks,
                answer=rag_result.answer,
                citations=rag_result.citations,
                refused=rag_result.refused,
                uncertainty=rag_result.uncertainty,
                dataset_question=ds_question,
                judge_result=judge,
                thresholds=protocol.thresholds.as_dict(),
            )

            question_results.append(
                QuestionResult(
                    question_id=ds_question.question_id,
                    question=ds_question.question,
                    question_type=ds_question.question_type,
                    answerable=ds_question.answerable,
                    expected_behavior=ds_question.expected_behavior,
                    expected_article=ds_question.expected_article,
                    source_chunk_id=ds_question.source_chunk_id,
                    retrieved_chunks=rag_result.retrieved_chunks,
                    answer=rag_result.answer,
                    citations=rag_result.citations,
                    refused=rag_result.refused,
                    uncertainty=rag_result.uncertainty,
                    metrics=validation.metrics,
                    red_line_failures=validation.red_line_failures,
                    failure_reasons=validation.failure_reasons,
                    judge_result=_judge_result_to_report(judge),
                    passed=validation.passed,
                )
            )

        if not question_results:
            err = EvaluationError(
                document_id=doc.document_id,
                stage="aggregation",
                stage_description="文档所有问题均为可恢复失败",
                error_type="ValueError",
                message=f"document {doc.document_id} has no successful questions",
                recoverable=False,
            )
            raise FatalEvaluationError(err)

        document_scorecards.append(
            aggregate_document(
                document_id=doc.document_id,
                title=doc.title,
                source_sha256=doc.source_sha256,
                content_class=doc.content_class,
                questions=question_results,
            )
        )

    report = aggregate_run(
        run_id=run_id,
        created_at=created_at,
        dataset=dataset_identity,
        protocol=protocol,
        system=system,
        documents=document_scorecards,
    )
    errors_report = ErrorReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=created_at,
        errors=errors,
    )

    # Schema self-check: re-validate through Pydantic before publishing.
    report = EvaluationReport.model_validate(report.model_dump())
    errors_report = ErrorReport.model_validate(errors_report.model_dump())

    run_dir = publisher(report, errors_report, reports_root)
    return RunResult(run_dir=run_dir, report=report, errors=errors_report)


def write_debug_bundle(
    run_id: str,
    fatal_error: EvaluationError,
    debug_root: Path = Path("var"),
) -> Path:
    """Write a desensitized debug bundle for a fatal evaluation failure."""
    debug_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = debug_root / f"eval_fatal_{run_id}_{timestamp}.json"
    data = {
        "run_id": run_id,
        "fatal_error": fatal_error.model_dump(mode="json"),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
