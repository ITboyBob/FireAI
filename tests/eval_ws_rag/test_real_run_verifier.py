from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.eval_ws_rag.dataset_models import DatasetDocument, DatasetQuestion, EvaluationDataset
from scripts.eval_ws_rag.dataset_store import load_dataset, save_dataset_atomic
from scripts.eval_ws_rag.report_models import ErrorReport
from scripts.eval_ws_rag.report_publisher import publish_run_atomic
from scripts.verify_ws_rag_evaluation_run import main as verify_main, verify_run


def _make_dataset(tmp_path: Path, document_id: str = "doc_a") -> Path:
    question = DatasetQuestion(
        question_id="q_001",
        question="问题？",
        question_type="frequent",
        answerable=True,
        expected_behavior="answer",
        expected_article="第一条",
        source_chunk_id="chunk_001",
        answer_sketch="摘要",
    )
    doc = DatasetDocument(
        document_id=document_id,
        title="测试法规",
        source_sha256="sha256_doc",
        content_class="S1",
        source_summary="W-S1 测试法规",
        questions=[question],
    )
    dataset = EvaluationDataset(
        schema_version="1.0.0",
        dataset_id="ds_001",
        dataset_fingerprint="placeholder",
        created_at=datetime.now(timezone.utc),
        generator_model="generator",
        generator_prompt_version="v1",
        generation_seed=42,
        documents=[doc],
    )
    root = tmp_path / "datasets"
    save_dataset_atomic(dataset, root)
    return root / dataset.dataset_id / "dataset.json"


def _make_report(tmp_path: Path, dataset_path: Path, run_id: str = "run_001"):
    from scripts.eval_ws_rag.report_models import (
        CitationRecord,
        DatasetIdentity,
        DocumentScorecard,
        EvaluationProtocol,
        EvaluationReport,
        EvaluatedSystem,
        JudgeDetail,
        JudgeResult,
        MetricScores,
        QuestionResult,
        RetrievedChunk,
        compute_protocol_fingerprint,
    )

    dataset = load_dataset(dataset_path)
    doc = dataset.documents[0]
    q = doc.questions[0]

    thresholds = MetricScores(
        context_relevancy=0.8,
        source_coverage=0.9,
        faithfulness=0.9,
        answer_relevance=0.8,
        citation_validity=1.0,
        refusal_appropriateness=0.9,
    )
    protocol = EvaluationProtocol(
        protocol_fingerprint=compute_protocol_fingerprint(
            judge_model="judge",
            judge_prompt_version="judge_v1",
            judge_repetitions=1,
            evidence_order_strategy="seed_shuffled",
            metric_algorithm_version="v1",
            thresholds=thresholds.as_dict(),
        ),
        judge_model="judge",
        judge_prompt_version="judge_v1",
        judge_repetitions=1,
        judge_calibrated=False,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
        answer_model="answer",
        answer_prompt_version="answer_v1",
        top_k=5,
    )

    question_result = QuestionResult(
        question_id=q.question_id,
        question=q.question,
        question_type=q.question_type,
        answerable=q.answerable,
        expected_behavior=q.expected_behavior,
        expected_article=q.expected_article,
        source_chunk_id=q.source_chunk_id,
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="chunk_001",
                document_id=doc.document_id,
                path="路径",
                text="文本",
                retrieval_score=0.9,
                keyword_score=0.8,
                vector_score=0.7,
                sources=["keyword"],
            )
        ],
        answer="答案。",
        citations=[CitationRecord(
            document_id=doc.document_id,
            path="路径",
            text="文本",
            matched_chunk_id="chunk_001",
            citation_label="路径",
        )],
        refused=False,
        uncertainty=None,
        metrics=MetricScores(
            context_relevancy=1.0,
            source_coverage=1.0,
            faithfulness=1.0,
            answer_relevance=1.0,
            citation_validity=1.0,
            refusal_appropriateness=1.0,
        ),
        red_line_failures=[],
        failure_reasons=[],
        judge_result=JudgeResult(
            context_relevancy=1.0,
            faithfulness=1.0,
            answer_relevance=1.0,
            details=[JudgeDetail(repetition=1)],
            prompt_version="judge_v1",
            model="judge",
        ),
        passed=True,
    )
    scorecard = DocumentScorecard(
        document_id=doc.document_id,
        title=doc.title,
        source_sha256=doc.source_sha256,
        content_class=doc.content_class,
        question_count=1,
        passed_questions=1,
        failed_questions_count=0,
        red_line_failures_count=0,
        metrics=question_result.metrics,
        overall_pass_rate=1.0,
        failed_questions=[],
        questions=[question_result],
    )
    report = EvaluationReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        dataset=DatasetIdentity(
            dataset_id=dataset.dataset_id,
            dataset_fingerprint=dataset.dataset_fingerprint,
            document_ids=[doc.document_id],
        ),
        protocol=protocol,
        system=EvaluatedSystem(
            git_commit="abc",
            git_dirty=False,
            corpus_fingerprint="cfp",
        ),
        summary=scorecard,
        documents=[scorecard],
    )
    errors = ErrorReport(
        schema_version="1.0.0",
        run_id=run_id,
        created_at=report.created_at,
        errors=[],
    )
    run_dir = publish_run_atomic(report, errors, tmp_path / "runs")
    return run_dir, report


def _setup_chunks(tmp_path: Path, document_id: str = "doc_a", source_sha256: str = "sha256_doc"):
    chunks_dir = tmp_path / "data" / "chunks"
    chunks_dir.mkdir(parents=True)
    chunk = {
        "chunk_id": "chunk_001",
        "document_id": document_id,
        "title": "测试法规",
        "text": "示例文本",
        "source_sha256": source_sha256,
        "extraction_class": "W",
        "content_class": "S1",
    }
    (chunks_dir / f"{document_id}.jsonl").write_text(
        __import__("json").dumps(chunk, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return chunks_dir


def test_verify_passes_valid_run(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    _setup_chunks(tmp_path)
    run_dir, report = _make_report(tmp_path, dataset_path)

    result = verify_run(dataset_path=dataset_path, run_dir=run_dir, data_dir=tmp_path / "data")
    assert result["run_id"] == "run_001"
    assert result["dataset_id"] == "ds_001"
    assert result["question_count"] == 1


def test_verify_rejects_missing_run_dir(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    with pytest.raises(ValueError):
        verify_run(dataset_path=dataset_path, run_dir=tmp_path / "no_such_run", data_dir=tmp_path / "data")


def test_verify_rejects_missing_errors_file(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    _setup_chunks(tmp_path)
    run_dir, _ = _make_report(tmp_path, dataset_path)
    (run_dir / "errors.json").unlink()
    with pytest.raises(ValueError):
        verify_run(dataset_path=dataset_path, run_dir=run_dir, data_dir=tmp_path / "data")


def test_verify_rejects_dataset_id_mismatch(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    _setup_chunks(tmp_path)
    run_dir, report = _make_report(tmp_path, dataset_path)
    # Reload report, change dataset id, rewrite.
    import json

    report_data = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_data["dataset"]["dataset_id"] = "ds_999"
    (run_dir / "report.json").write_text(json.dumps(report_data), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_run(dataset_path=dataset_path, run_dir=run_dir, data_dir=tmp_path / "data")


def test_verify_rejects_source_sha256_mismatch(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    _setup_chunks(tmp_path, source_sha256="different_sha")
    run_dir, _ = _make_report(tmp_path, dataset_path)
    with pytest.raises(ValueError):
        verify_run(dataset_path=dataset_path, run_dir=run_dir, data_dir=tmp_path / "data")


def test_verify_cli_returns_zero_on_valid_run(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    _setup_chunks(tmp_path)
    run_dir, _ = _make_report(tmp_path, dataset_path)
    code = verify_main([
        "--dataset", str(dataset_path),
        "--run", str(run_dir),
        "--data-dir", str(tmp_path / "data"),
    ])
    assert code == 0


def test_verify_cli_returns_nonzero_on_bad_run(tmp_path: Path):
    dataset_path = _make_dataset(tmp_path)
    code = verify_main([
        "--dataset", str(dataset_path),
        "--run", str(tmp_path / "no_such_run"),
        "--data-dir", str(tmp_path / "data"),
    ])
    assert code == 1
