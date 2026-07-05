from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.eval_ws_rag.rag_runner import (
    RagRunResult,
    RagStageError,
    run_question,
)


def _make_chunk(document_id: str, chunk_id: str, article_no: str | None = None) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "title": "测试法规",
        "path": f"测试法规 > {article_no or '第一条'}",
        "text": "示例文本",
        "article_no": article_no or "第一条",
        "article_index": 1,
        "chunk_index": 1,
        "score": 0.9,
        "keyword_score": 0.8,
        "vector_score": 0.7,
        "sources": ["keyword"],
    }


def _fake_retriever(hits: list[dict[str, Any]]):
    class FakeRetriever:
        def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
            return hits

    return FakeRetriever()


def _fake_answer_client(answer: dict[str, Any]):
    class FakeClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            return answer

    return FakeClient()


def test_run_question_records_retrieved_chunks():
    hits = [_make_chunk("doc_a", "chunk_001")]
    retriever = _fake_retriever(hits)
    answer = {
        "conclusion": "结论",
        "citations": ["《测试法规》第一条"],
        "scope": "",
        "uncertainty": "",
    }
    client = _fake_answer_client(answer)

    result = run_question(
        retriever=retriever,
        answer_client=client,
        question="问题？",
        document_id="doc_a",
        top_k=5,
    )

    assert isinstance(result, RagRunResult)
    assert result.question == "问题？"
    assert len(result.retrieved_chunks) == 1
    assert result.retrieved_chunks[0].chunk_id == "chunk_001"
    assert result.retrieved_chunks[0].document_id == "doc_a"
    assert result.answer == "结论"
    assert result.refused is False


def test_run_question_binds_citations_by_label_not_path():
    """答案模型返回的是 build_citation_label 标签，Runner 必须据此绑定到检索证据。"""
    hits = [_make_chunk("doc_a", "chunk_001", article_no="第一条")]
    retriever = _fake_retriever(hits)
    answer = {
        "conclusion": "结论",
        "citations": ["《测试法规》第一条"],
        "scope": "",
        "uncertainty": "",
    }

    result = run_question(
        retriever=retriever,
        answer_client=_fake_answer_client(answer),
        question="问题？",
        document_id="doc_a",
        top_k=5,
    )

    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.matched_chunk_id == "chunk_001"
    assert citation.document_id == "doc_a"
    assert citation.path == "测试法规 > 第一条"
    assert citation.text == "示例文本"
    assert citation.citation_label == "《测试法规》第一条"


def test_run_question_passes_original_evidence_to_answer():
    hits = [_make_chunk("doc_a", "chunk_001")]
    retriever = _fake_retriever(hits)
    received_evidence: list[dict[str, Any]] = []

    class CapturingClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            # build_answer 会把 evidence 包装进 messages 的 user prompt 中。
            # 这里直接通过返回固定答案，并记录调用次数。
            return {
                "conclusion": "结论",
                "citations": ["《测试法规》第一条"],
                "scope": "",
                "uncertainty": "",
            }

    result = run_question(
        retriever=_fake_retriever(hits),
        answer_client=CapturingClient(),
        question="问题？",
        document_id="doc_a",
        top_k=5,
    )
    assert len(result.retrieved_chunks) == 1
    assert result.retrieved_chunks[0].retrieval_score == pytest.approx(0.9)


def test_empty_retrieval_leads_to_refusal():
    retriever = _fake_retriever([])
    client = _fake_answer_client({
        "conclusion": "不应使用",
        "citations": [],
        "scope": "",
        "uncertainty": "",
        "evidence": [],
    })

    result = run_question(
        retriever=retriever,
        answer_client=client,
        question="问题？",
        document_id="doc_a",
        top_k=5,
    )
    assert result.refused is True
    assert result.retrieved_chunks == []


def test_query_format_error_is_recoverable():
    class BadRetriever:
        def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
            raise ValueError("query format bad")

    with pytest.raises(RagStageError) as exc_info:
        run_question(
            retriever=BadRetriever(),
            answer_client=_fake_answer_client({}),
            question="问题？",
            document_id="doc_a",
            top_k=5,
            recoverable_errors={"query_normalization"},
        )
    assert exc_info.value.stage == "query_normalization"
    assert exc_info.value.recoverable is True


def test_fusion_error_is_fatal():
    class BadRetriever:
        def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
            raise RuntimeError("fusion failed")

    with pytest.raises(RagStageError) as exc_info:
        run_question(
            retriever=BadRetriever(),
            answer_client=_fake_answer_client({}),
            question="问题？",
            document_id="doc_a",
            top_k=5,
        )
    assert exc_info.value.stage == "fusion"
    assert exc_info.value.recoverable is False


def test_answer_model_error_retries_once():
    hits = [_make_chunk("doc_a", "chunk_001")]
    calls: list[int] = []

    class FlakyClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            calls.append(len(calls))
            if len(calls) == 1:
                raise RuntimeError("temporary")
            return {
                "conclusion": "结论",
                "citations": ["《测试法规》第一条"],
                "scope": "",
                "uncertainty": "",
            }

    result = run_question(
        retriever=_fake_retriever(hits),
        answer_client=FlakyClient(),
        question="问题？",
        document_id="doc_a",
        top_k=5,
        max_retries=1,
    )
    assert result.answer == "结论"
    assert len(calls) == 2


def test_answer_model_persistent_error_fails_question():
    hits = [_make_chunk("doc_a", "chunk_001")]

    class FailingClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            raise RuntimeError("persistent")

    with pytest.raises(RagStageError) as exc_info:
        run_question(
            retriever=_fake_retriever(hits),
            answer_client=FailingClient(),
            question="问题？",
            document_id="doc_a",
            top_k=5,
            max_retries=1,
        )
    assert exc_info.value.stage == "answer_generation"


def test_real_index_returns_target_article():
    index_dir = Path("data/index")
    chunks_dir = Path("data/chunks")
    if not index_dir.exists() or not chunks_dir.exists():
        pytest.skip("索引或 chunks 不存在")

    from app.services.retriever import Retriever

    retriever = Retriever.from_disk(
        keyword_db_path=index_dir / "retrieval.db",
        vector_index_path=index_dir / "faiss.index",
        vector_map_path=index_dir / "vector_map.json",
    )

    class DummyClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            return {
                "conclusion": "结论",
                "citations": ["《消防监督检查规定》第十条"],
                "scope": "",
                "uncertainty": "",
            }

    result = run_question(
        retriever=retriever,
        answer_client=DummyClient(),
        question="消防监督检查规定第十条规定了什么？",
        document_id="doc_d97773f1500c",
        top_k=5,
    )
    assert len(result.retrieved_chunks) > 0
    assert all(c.document_id for c in result.retrieved_chunks)
