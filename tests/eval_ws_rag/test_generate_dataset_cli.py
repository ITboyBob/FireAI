from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.generate_ws_rag_dataset as dataset_cli
from scripts.eval_ws_rag.question_generator import QuestionGeneratorClient


def _make_chunks() -> list[dict]:
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


def _generated_question(question_type: str, answerable: bool, **overrides):
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


def _fake_client_for_three_types():
    responses = [
        _generated_question("frequent", answerable=True),
        _generated_question("boundary", answerable=False, expected_article=None),
        _generated_question("diversity", answerable=True, expected_article="第二条"),
    ]

    def complete(messages):
        return {"questions": responses}

    return QuestionGeneratorClient(complete=complete)


def test_cli_requires_document_id():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with pytest.raises(SystemExit):
            dataset_cli.main(
                [
                    "--dataset-id",
                    "ds_test",
                    "--seed",
                    "42",
                    "--output-dir",
                    str(tmp_path),
                ]
            )


def test_cli_creates_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "doc_a.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in _make_chunks()), encoding="utf-8"
        )
        output_dir = tmp_path / "datasets"

        with patch.object(
            dataset_cli,
            "_build_question_generator_client",
            return_value=_fake_client_for_three_types(),
        ):
            rc = dataset_cli.main(
                [
                    "--document-id",
                    "doc_a",
                    "--dataset-id",
                    "ds_cli_test",
                    "--seed",
                    "42",
                    "--chunks-dir",
                    str(chunks_dir),
                    "--output-dir",
                    str(output_dir),
                ]
            )
        assert rc == 0
        dataset_path = output_dir / "ds_cli_test" / "dataset.json"
        assert dataset_path.exists()
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        assert data["dataset_id"] == "ds_cli_test"
        assert len(data["documents"]) == 1
        assert len(data["documents"][0]["questions"]) == 3
        types = {q["question_type"] for q in data["documents"][0]["questions"]}
        assert types == {"frequent", "boundary", "diversity"}


def test_cli_does_not_run_rag():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "doc_a.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in _make_chunks()), encoding="utf-8"
        )
        output_dir = tmp_path / "datasets"

        with patch.object(
            dataset_cli,
            "_build_question_generator_client",
            return_value=_fake_client_for_three_types(),
        ):
            rc = dataset_cli.main(
                [
                    "--document-id",
                    "doc_a",
                    "--dataset-id",
                    "ds_cli_no_rag",
                    "--seed",
                    "42",
                    "--chunks-dir",
                    str(chunks_dir),
                    "--output-dir",
                    str(output_dir),
                ]
            )
        assert rc == 0
        dataset_path = output_dir / "ds_cli_no_rag" / "dataset.json"
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        for doc in data["documents"]:
            for q in doc["questions"]:
                assert "retrieved_chunks" not in q
                assert "answer" not in q


def test_cli_generates_globally_unique_question_ids():
    """回归：两份文档的 question_id 必须在 dataset 内全局唯一。"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()
        for doc_id in ("doc_a", "doc_b"):
            chunks = _make_chunks()
            for chunk in chunks:
                chunk["document_id"] = doc_id
            (chunks_dir / f"{doc_id}.jsonl").write_text(
                "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks),
                encoding="utf-8",
            )
        output_dir = tmp_path / "datasets"

        with patch.object(
            dataset_cli,
            "_build_question_generator_client",
            return_value=_fake_client_for_three_types(),
        ):
            rc = dataset_cli.main(
                [
                    "--document-id", "doc_a",
                    "--document-id", "doc_b",
                    "--dataset-id", "ds_unique_ids",
                    "--seed", "42",
                    "--chunks-dir", str(chunks_dir),
                    "--output-dir", str(output_dir),
                ]
            )
        assert rc == 0
        dataset_path = output_dir / "ds_unique_ids" / "dataset.json"
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        ids = [q["question_id"] for doc in data["documents"] for q in doc["questions"]]
        assert len(ids) == 6
        assert len(ids) == len(set(ids))


def test_real_chunks_fingerprint_stable():
    chunks_dir = Path("data/chunks")
    if not chunks_dir.exists():
        pytest.skip("chunks 目录不存在")

    target_docs = ["doc_d97773f1500c", "doc_0e84d13a099b"]
    for document_id in target_docs:
        file_path = chunks_dir / f"{document_id}.jsonl"
        if not file_path.exists():
            pytest.skip(f"{document_id} 不存在")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_dir = tmp_path / "datasets"

        def fake_complete(messages):
            # 从 messages 中推断当前请求的问题类型和第一个真实 chunk_id。
            content = messages[-1]["content"]
            if "frequent" in content:
                qtype = "frequent"
            elif "boundary" in content or "拒答" in content:
                qtype = "boundary"
            else:
                qtype = "diversity"
            first_chunk_id = "chunk_001"
            for line in content.splitlines():
                if line.startswith("- chunk_id: "):
                    first_chunk_id = line.split("- chunk_id: ", 1)[1].strip()
                    break
            return {
                "questions": [
                    {
                        "question": f"{qtype} 问题？",
                        "question_type": qtype,
                        "answerable": qtype != "boundary",
                        "expected_behavior": "refuse" if qtype == "boundary" else "answer",
                        "expected_article": None if qtype == "boundary" else "第一条",
                        "source_chunk_id": first_chunk_id,
                        "answer_sketch": "摘要",
                    }
                ]
            }

        client = QuestionGeneratorClient(complete=fake_complete)
        with patch.object(
            dataset_cli,
            "_build_question_generator_client",
            return_value=client,
        ):
            rc = dataset_cli.main(
                [
                    "--document-id",
                    "doc_d97773f1500c",
                    "--document-id",
                    "doc_0e84d13a099b",
                    "--dataset-id",
                    "ds_real_chunks",
                    "--seed",
                    "42",
                    "--chunks-dir",
                    str(chunks_dir),
                    "--output-dir",
                    str(output_dir),
                    "--frequent",
                    "1",
                    "--boundary",
                    "1",
                    "--diversity",
                    "1",
                ]
            )
        assert rc == 0

        dataset_path = output_dir / "ds_real_chunks" / "dataset.json"
        assert dataset_path.exists()
        data1 = json.loads(dataset_path.read_text(encoding="utf-8"))
        data2 = json.loads(dataset_path.read_text(encoding="utf-8"))
        assert data1["dataset_fingerprint"] == data2["dataset_fingerprint"]
