from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.eval_ws_rag.dataset_models import EvaluationDataset
from scripts.eval_ws_rag.dataset_store import (
    canonical_dataset_payload,
    compute_dataset_fingerprint,
    load_dataset,
    save_dataset_atomic,
)


def _make_minimal_dataset(fingerprint: str | None = None, **overrides) -> EvaluationDataset:
    return EvaluationDataset(
        schema_version="1.0.0",
        dataset_id="ds_test_001",
        dataset_fingerprint=fingerprint or "placeholder",
        created_at=datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
        generator_model="deepseek-v4-pro-260425",
        generator_prompt_version="qg_v1",
        generation_seed=42,
        documents=[
            {
                "document_id": "doc_d97773f1500c",
                "title": "消防监督检查规定",
                "source_sha256": "sha256_doc_d97773f1500c",
                "content_class": "S1",
                "source_summary": "W-S1 消防监督检查规定",
                "questions": [
                    {
                        "question_id": "q_frequent_001",
                        "question": "消防监督检查规定第十条规定了什么？",
                        "question_type": "frequent",
                        "answerable": True,
                        "expected_behavior": "answer",
                        "expected_article": "第十条",
                        "source_chunk_id": "chunk_001",
                        "answer_sketch": "规定公安机关消防机构应定期监督检查。",
                    }
                ],
            }
        ],
        **overrides,
    )


def test_canonical_payload_is_deterministic():
    payload1 = canonical_dataset_payload(_make_minimal_dataset())
    payload2 = canonical_dataset_payload(_make_minimal_dataset())
    assert payload1 == payload2


def test_fingerprint_ignores_key_order():
    raw = json.loads(canonical_dataset_payload(_make_minimal_dataset()))
    shuffled = json.loads(canonical_dataset_payload(_make_minimal_dataset()))
    # 改变字典键顺序后重算 fingerprint
    shuffled["documents"][0]["questions"][0] = dict(
        reversed(list(shuffled["documents"][0]["questions"][0].items()))
    )
    fp1 = compute_dataset_fingerprint(json.dumps(raw, sort_keys=True, ensure_ascii=False))
    fp2 = compute_dataset_fingerprint(json.dumps(shuffled, sort_keys=True, ensure_ascii=False))
    assert fp1 == fp2


def test_fingerprint_ignores_created_at():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.created_at = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) == compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_fingerprint_changes_on_question_text():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.documents[0].questions[0].question = "变了的问题？"
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) != compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_fingerprint_changes_on_expected_article():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.documents[0].questions[0].expected_article = "第十一条"
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) != compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_fingerprint_changes_on_expected_behavior():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.documents[0].questions[0].expected_behavior = "refuse"
    ds2.documents[0].questions[0].expected_article = None
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) != compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_fingerprint_changes_on_source_chunk_id():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.documents[0].questions[0].source_chunk_id = "chunk_002"
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) != compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_fingerprint_changes_on_source_summary():
    ds1 = _make_minimal_dataset()
    ds2 = _make_minimal_dataset()
    ds2.documents[0].source_summary = "变了"
    assert compute_dataset_fingerprint(canonical_dataset_payload(ds1)) != compute_dataset_fingerprint(
        canonical_dataset_payload(ds2)
    )


def test_save_dataset_atomic_and_refuse_overwrite():
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        ds = _make_minimal_dataset()
        save_dataset_atomic(ds, root_path)

        dataset_path = root_path / "ds_test_001" / "dataset.json"
        assert dataset_path.exists()
        loaded = load_dataset(dataset_path)
        assert loaded.dataset_id == ds.dataset_id
        assert loaded.dataset_fingerprint == ds.dataset_fingerprint

        with pytest.raises(FileExistsError):
            save_dataset_atomic(ds, root_path)


def test_dataset_rejects_duplicate_question_ids_across_documents():
    """契约第 10 条：每个 question_id 在 dataset 内唯一，跨文档重号必须拒绝。"""
    question = {
        "question_id": "q_frequent_001",
        "question": "同一 ID 的问题？",
        "question_type": "frequent",
        "answerable": True,
        "expected_behavior": "answer",
        "expected_article": "第十条",
        "source_chunk_id": "chunk_001",
        "answer_sketch": "摘要",
    }
    documents = [
        {
            "document_id": "doc_a",
            "title": "法规A",
            "source_sha256": "sha_a",
            "content_class": "S1",
            "source_summary": "",
            "questions": [question],
        },
        {
            "document_id": "doc_b",
            "title": "法规B",
            "source_sha256": "sha_b",
            "content_class": "S2",
            "source_summary": "",
            "questions": [question],
        },
    ]
    with pytest.raises(ValidationError, match="question_id"):
        EvaluationDataset(
            schema_version="1.0.0",
            dataset_id="ds_dup_qid",
            dataset_fingerprint="placeholder",
            created_at=datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
            generator_model="deepseek-v4-pro-260425",
            generator_prompt_version="qg_v1",
            generation_seed=42,
            documents=documents,
        )


def test_load_dataset_detects_fingerprint_mismatch():
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        ds = _make_minimal_dataset()
        save_dataset_atomic(ds, root_path)

        dataset_path = root_path / "ds_test_001" / "dataset.json"
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        data["documents"][0]["questions"][0]["question"] = "被篡改的问题"
        dataset_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        with pytest.raises(ValueError, match="fingerprint"):
            load_dataset(dataset_path)


def test_real_chunk_compatibility():
    chunk_path = Path("data/chunks/doc_d97773f1500c.jsonl")
    if not chunk_path.exists():
        pytest.skip("真实 chunk 不存在")

    first_line = json.loads(chunk_path.read_text(encoding="utf-8").splitlines()[0])
    doc_id = first_line.get("document_id")
    source_sha256 = first_line.get("source_sha256")
    content_class = first_line.get("content_class")

    ds = EvaluationDataset(
        schema_version="1.0.0",
        dataset_id="ds_real_chunk_compat",
        dataset_fingerprint="placeholder",
        created_at=datetime.now(timezone.utc),
        generator_model="deepseek-v4-pro-260425",
        generator_prompt_version="qg_v1",
        generation_seed=42,
        documents=[
            {
                "document_id": doc_id,
                "title": first_line.get("title", ""),
                "source_sha256": source_sha256,
                "content_class": content_class,
                "source_summary": "真实兼容性测试",
                "questions": [
                    {
                        "question_id": "q_compat_001",
                        "question": "测试问题？",
                        "question_type": "frequent",
                        "answerable": True,
                        "expected_behavior": "answer",
                        "expected_article": first_line.get("article_no"),
                        "source_chunk_id": first_line.get("chunk_id", "chunk_compat_001"),
                        "answer_sketch": "测试摘要",
                    }
                ],
            }
        ],
    )

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        save_dataset_atomic(ds, root_path)
        loaded = load_dataset(root_path / "ds_real_chunk_compat" / "dataset.json")
        assert loaded.dataset_fingerprint == compute_dataset_fingerprint(
            canonical_dataset_payload(loaded)
        )
