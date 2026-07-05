from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.answer_service import build_answer
from app.services.query_normalizer import normalize_query
from scripts.eval_ws_rag.report_models import CitationRecord, RetrievedChunk


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]: ...


class ChatClient(Protocol):
    def complete(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]: ...


@dataclass
class RagRunResult:
    question: str
    document_id: str
    retrieved_chunks: list[RetrievedChunk]
    answer: str
    citations: list[CitationRecord]
    refused: bool
    uncertainty: str | None
    answer_model: str
    duration_seconds: float


@dataclass
class RagStageError(RuntimeError):
    stage: str
    stage_description: str
    error_type: str
    message: str
    recoverable: bool


def run_question(
    *,
    retriever: Retriever,
    answer_client: ChatClient,
    question: str,
    document_id: str,
    top_k: int = 5,
    answer_model: str = "",
    max_retries: int = 1,
    recoverable_errors: set[str] | None = None,
) -> RagRunResult:
    """Run a single question through the real RAG pipeline.

    The Retriever.search() output is recorded verbatim. Empty retrieval is not
    treated as an error; it flows into build_answer() to test refusal behavior.
    """
    recoverable_errors = recoverable_errors or set()
    start_time = time.perf_counter()

    try:
        normalized = normalize_query(question)
    except Exception as exc:
        raise RagStageError(
            stage="query_normalization",
            stage_description="查询规范化失败",
            error_type=type(exc).__name__,
            message=str(exc),
            recoverable="query_normalization" in recoverable_errors,
        ) from exc

    try:
        hits = retriever.search(question, top_k=top_k)
    except Exception as exc:
        # Classify based on exception message heuristics.
        message = str(exc).lower()
        if "query" in message or "normaliz" in message or "parse" in message or "format" in message:
            stage = "query_normalization"
        elif "keyword" in message or "sql" in message or "retrieval.db" in message:
            stage = "keyword_search"
        elif "vector" in message or "faiss" in message or "encode" in message or "dimension" in message:
            stage = "vector_search"
        elif "fuse" in message or "fusion" in message or "weight" in message:
            stage = "fusion"
        else:
            stage = "retrieval"
        raise RagStageError(
            stage=stage,
            stage_description="检索阶段失败",
            error_type=type(exc).__name__,
            message=str(exc),
            recoverable=stage in recoverable_errors,
        ) from exc

    retrieved_chunks = _normalize_retrieved_chunks(hits)

    try:
        answer = _build_answer_with_retry(
            evidence=hits,
            client=answer_client,
            question=question,
            max_retries=max_retries,
        )
    except RagStageError:
        raise
    except Exception as exc:
        raise RagStageError(
            stage="answer_generation",
            stage_description="答案生成模型调用失败",
            error_type=type(exc).__name__,
            message=str(exc),
            recoverable="answer_generation" in recoverable_errors,
        ) from exc

    fields = _extract_answer_fields(answer)
    duration = time.perf_counter() - start_time

    return RagRunResult(
        question=question,
        document_id=document_id,
        retrieved_chunks=retrieved_chunks,
        answer=fields["answer"],
        citations=fields["citations"],
        refused=fields["refused"],
        uncertainty=fields["uncertainty"],
        answer_model=answer_model,
        duration_seconds=duration,
    )


def _build_answer_with_retry(
    *,
    evidence: Sequence[dict[str, Any]],
    client: ChatClient,
    question: str,
    max_retries: int,
) -> dict[str, Any]:
    from app.services.answer_service import (
        EMPTY_EVIDENCE_UNCERTAINTY,
        INVALID_CITATION_UNCERTAINTY,
        is_model_failure_uncertainty,
    )

    last_failure: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            answer = build_answer(evidence=evidence, client=client, question=question)
        except Exception as exc:
            last_failure = exc
            if attempt < max_retries and _is_retryable_error(exc):
                time.sleep(0.01)
                continue
            raise RagStageError(
                stage="answer_generation",
                stage_description="答案生成模型调用失败",
                error_type=type(exc).__name__,
                message=str(exc),
                recoverable=False,
            ) from exc

        # Empty evidence refusal is expected and not a model failure.
        if not evidence:
            return answer

        conclusion = str(answer.get("conclusion", "")).strip()
        uncertainty = str(answer.get("uncertainty", "")).strip()
        from app.services.answer_service import REFUSAL_CONCLUSION

        is_refusal = conclusion == REFUSAL_CONCLUSION
        if not is_refusal:
            return answer

        # Citation/empty-uncertainty refusals are answer-quality issues, not model-call failures.
        if uncertainty in (EMPTY_EVIDENCE_UNCERTAINTY, INVALID_CITATION_UNCERTAINTY):
            return answer

        if is_model_failure_uncertainty(uncertainty):
            last_failure = RuntimeError(f"model failure: {uncertainty}")
            if attempt < max_retries:
                time.sleep(0.01)
                continue
            break

        # Other refusal: return as-is.
        return answer

    if last_failure is not None:
        raise RagStageError(
            stage="answer_generation",
            stage_description="答案生成模型调用失败",
            error_type=type(last_failure).__name__,
            message=str(last_failure),
            recoverable=False,
        ) from last_failure
    raise RagStageError(
        stage="answer_generation",
        stage_description="答案生成模型调用失败",
        error_type="Unknown",
        message="unknown answer generation failure",
        recoverable=False,
    )


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "rate limit" in message
        or "429" in message
        or "timeout" in message
        or "connection" in message
        or "temporary" in message
    )


def _normalize_retrieved_chunks(hits: Sequence[dict[str, Any]]) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for hit in hits:
        chunk = RetrievedChunk(
            chunk_id=str(hit.get("chunk_id", "")),
            document_id=str(hit.get("document_id", "")),
            path=str(hit.get("path", "")),
            text=str(hit.get("text", "")),
            retrieval_score=float(hit.get("score", 0.0)),
            keyword_score=float(hit.get("keyword_score", 0.0)),
            vector_score=float(hit.get("vector_score", 0.0)),
            sources=list(hit.get("sources", [])) if isinstance(hit.get("sources"), list) else [],
        )
        chunks.append(chunk)
    return chunks


def _extract_answer_fields(answer: dict[str, Any]) -> dict[str, Any]:
    from app.services.answer_service import REFUSAL_CONCLUSION

    conclusion = str(answer.get("conclusion", ""))
    return {
        "answer": conclusion,
        "citations": _normalize_citations(answer.get("citations", []), answer.get("evidence", [])),
        "refused": conclusion.strip() == REFUSAL_CONCLUSION,
        "uncertainty": answer.get("uncertainty") if answer.get("uncertainty") else None,
    }


def _normalize_citations(raw_citations: Any, evidence: Sequence[dict[str, Any]]) -> list[CitationRecord]:
    if not raw_citations:
        return []
    records: list[CitationRecord] = []
    evidence_by_path = {str(item.get("path", "")): item for item in evidence}
    for raw in raw_citations:
        text = str(raw)
        matched = evidence_by_path.get(text)
        records.append(
            CitationRecord(
                document_id=str(matched.get("document_id", "")) if matched else "",
                path=text,
                text=str(matched.get("text", "")) if matched else "",
                matched_chunk_id=str(matched.get("chunk_id", "")) if matched else "",
                citation_label=text,
            )
        )
    return records
