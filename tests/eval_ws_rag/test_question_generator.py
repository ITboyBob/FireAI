from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from scripts.eval_ws_rag.dataset_models import DatasetDocument, EvaluationDataset
from scripts.eval_ws_rag.question_generator import (
    GeneratedQuestion,
    QuestionGenerationError,
    QuestionGeneratorClient,
    generate_document_questions,
)


def _fake_complete(response_questions: list[dict[str, Any]]):
    """Return a fake complete callable that returns a structured response."""

    def complete(messages: list[dict[str, str]]) -> dict[str, Any]:
        return {"questions": response_questions}

    return complete


def _generated_question(question_type: str, answerable: bool, **overrides) -> dict[str, Any]:
    return {
        "question": f"{question_type} 问题？",
        "question_type": question_type,
        "answerable": answerable,
        "expected_behavior": "answer" if answerable else "refuse",
        "expected_article": "第一条" if answerable else None,
        "source_chunk_id": "chunk_001",
        "answer_sketch": "摘要",
        **overrides,
    }


def _make_chunks() -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": "chunk_001",
            "document_id": "doc_a",
            "title": "测试法规",
            "path": "测试法规 > 第一条",
            "text": "这是第一条内容。",
            "article_no": "第一条",
            "article_index": 1,
            "chunk_index": 1,
            "source_sha256": "sha256_doc_a",
            "extraction_class": "W",
            "content_class": "S1",
        },
        {
            "chunk_id": "chunk_002",
            "document_id": "doc_a",
            "title": "测试法规",
            "path": "测试法规 > 第二条",
            "text": "这是第二条内容。",
            "article_no": "第二条",
            "article_index": 2,
            "chunk_index": 1,
            "source_sha256": "sha256_doc_a",
            "extraction_class": "W",
            "content_class": "S1",
        },
    ]


def test_generates_three_types():
    chunks = _make_chunks()
    responses = [
        _generated_question("frequent", answerable=True, expected_article="第一条"),
        _generated_question("boundary", answerable=False, expected_article=None),
        _generated_question("diversity", answerable=True, expected_article="第二条"),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 1, "boundary": 1, "diversity": 1},
        seed=42,
    )
    assert len(questions) == 3
    types = {q.question_type for q in questions}
    assert types == {"frequent", "boundary", "diversity"}


def test_stable_question_ids():
    chunks = _make_chunks()
    responses = [
        _generated_question("frequent", answerable=True),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    questions1 = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 1, "boundary": 0, "diversity": 0},
        seed=42,
    )
    questions2 = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 1, "boundary": 0, "diversity": 0},
        seed=42,
    )
    assert [q.question_id for q in questions1] == [q.question_id for q in questions2]


def test_deduplicates_questions():
    chunks = _make_chunks()
    responses = [
        _generated_question("frequent", answerable=True, question="重复问题？"),
        _generated_question("frequent", answerable=True, question="重复问题？"),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 2, "boundary": 0, "diversity": 0},
        seed=42,
    )
    assert len(questions) == 1


def test_answerable_must_have_existing_article():
    chunks = _make_chunks()
    responses = [
        _generated_question("frequent", answerable=True, expected_article="第九十九条"),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    with pytest.raises(QuestionGenerationError, match="article"):
        generate_document_questions(
            client=client,
            chunks=chunks,
            document_id="doc_a",
            counts={"frequent": 1, "boundary": 0, "diversity": 0},
            seed=42,
        )


def test_unanswerable_must_not_have_existing_article():
    chunks = _make_chunks()
    responses = [
        _generated_question("boundary", answerable=False, expected_article="第一条"),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    with pytest.raises(QuestionGenerationError, match="boundary"):
        generate_document_questions(
            client=client,
            chunks=chunks,
            document_id="doc_a",
            counts={"frequent": 0, "boundary": 1, "diversity": 0},
            seed=42,
        )


def test_rejects_invalid_schema_response():
    chunks = _make_chunks()

    def bad_complete(messages: list[dict[str, str]]) -> dict[str, Any]:
        return {"questions": [{"question": "缺字段"}]}

    client = QuestionGeneratorClient(complete=bad_complete)
    with pytest.raises(QuestionGenerationError):
        generate_document_questions(
            client=client,
            chunks=chunks,
            document_id="doc_a",
            counts={"frequent": 1, "boundary": 0, "diversity": 0},
            seed=42,
        )


def test_question_ids_unique_across_documents():
    """回归：跨文档连续编号时问题 ID 在 dataset 内全局唯一。"""
    chunks = _make_chunks()
    responses = [
        _generated_question("frequent", answerable=True),
        _generated_question("boundary", answerable=False),
        _generated_question("diversity", answerable=True, expected_article="第二条"),
    ]
    client = QuestionGeneratorClient(complete=_fake_complete(responses))
    counts = {"frequent": 1, "boundary": 1, "diversity": 1}

    doc1_questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts=counts,
        seed=42,
        start_index=1,
    )
    doc2_questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_b",
        counts=counts,
        seed=42,
        start_index=len(doc1_questions) + 1,
    )

    ids = [q.question_id for q in doc1_questions + doc2_questions]
    assert len(ids) == 6
    assert len(ids) == len(set(ids))


def test_serial_calls_and_retry_once():
    chunks = _make_chunks()
    calls: list[int] = []

    def flaky_complete(messages: list[dict[str, str]]) -> dict[str, Any]:
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return {"questions": [_generated_question("frequent", answerable=True)]}

    client = QuestionGeneratorClient(complete=flaky_complete, max_retries=1)
    questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 1, "boundary": 0, "diversity": 0},
        seed=42,
    )
    assert len(questions) == 1
    assert len(calls) == 2


def test_retry_exhausted_raises():
    chunks = _make_chunks()

    def failing_complete(messages: list[dict[str, str]]) -> dict[str, Any]:
        raise RuntimeError("persistent failure")

    client = QuestionGeneratorClient(complete=failing_complete, max_retries=1)
    with pytest.raises(QuestionGenerationError):
        generate_document_questions(
            client=client,
            chunks=chunks,
            document_id="doc_a",
            counts={"frequent": 1, "boundary": 0, "diversity": 0},
            seed=42,
        )


def test_no_api_key_in_dataset():
    chunks = _make_chunks()
    client = QuestionGeneratorClient(complete=_fake_complete([_generated_question("frequent", answerable=True)]))
    questions = generate_document_questions(
        client=client,
        chunks=chunks,
        document_id="doc_a",
        counts={"frequent": 1, "boundary": 0, "diversity": 0},
        seed=42,
    )
    dataset = EvaluationDataset(
        schema_version="1.0.0",
        dataset_id="ds_test",
        dataset_fingerprint="fp",
        created_at=datetime.now(timezone.utc),
        generator_model="model",
        generator_prompt_version="v1",
        generation_seed=42,
        documents=[
            DatasetDocument(
                document_id="doc_a",
                title="测试法规",
                source_sha256="sha256_doc_a",
                content_class="S1",
                source_summary="摘要",
                questions=questions,
            )
        ],
    )
    payload = json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False)
    assert "api_key" not in payload.lower()
    assert "sk-" not in payload
