from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts.eval_ws_rag.dataset_models import DatasetDocument, DatasetQuestion, EvaluationDataset
from scripts.eval_ws_rag.dataset_store import save_dataset_atomic
from scripts.eval_ws_rag.eval_chat_client import EvalClientError
from scripts.eval_ws_rag.llm_judge import JudgeDetail, JudgeResult
from scripts.eval_ws_rag.orchestrator import (
    FatalEvaluationError,
    compute_corpus_fingerprint,
    load_config,
    run_evaluation,
)
from scripts.eval_ws_rag.report_publisher import publish_run_atomic


def _make_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "thresholds": {
            "context_relevancy": 0.8,
            "source_coverage": 0.9,
            "faithfulness": 0.9,
            "answer_relevance": 0.8,
            "citation_validity": 1.0,
            "refusal_appropriateness": 0.9,
        },
        "default_top_k": 5,
        "default_judge_repetitions": 1,
        "default_judge_temperature": 0,
        "default_max_retries": 1,
        "default_concurrency": 1,
    }


def _make_dataset(tmp_path: Path, questions: list[DatasetQuestion] | None = None) -> EvaluationDataset:
    if questions is None:
        questions = [
            DatasetQuestion(
                question_id="q_001",
                question="问题？",
                question_type="frequent",
                answerable=True,
                expected_behavior="answer",
                expected_article="第一条",
                source_chunk_id="chunk_001",
                answer_sketch="摘要",
            )
        ]
    doc = DatasetDocument(
        document_id="doc_a",
        title="测试法规",
        source_sha256="sha256_doc_a",
        content_class="S1",
        source_summary="W-S1 测试法规",
        questions=questions,
    )
    dataset = EvaluationDataset(
        schema_version="1.0.0",
        dataset_id="ds_001",
        dataset_fingerprint="placeholder",
        created_at=datetime.now(timezone.utc),
        generator_model="generator_model",
        generator_prompt_version="generator_v1",
        generation_seed=42,
        documents=[doc],
    )
    return dataset


def _persist_dataset(tmp_path: Path, dataset: EvaluationDataset | None = None) -> Path:
    if dataset is None:
        dataset = _make_dataset(tmp_path)
    root = tmp_path / "datasets"
    save_dataset_atomic(dataset, root)
    return root / dataset.dataset_id / "dataset.json"


def _setup_data_dir(tmp_path: Path, document_ids: list[str]) -> Path:
    data_dir = tmp_path / "data"
    chunks_dir = data_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    index_dir = data_dir / "index"
    index_dir.mkdir(parents=True)
    for name in ["retrieval.db", "faiss.index", "vector_map.json"]:
        (index_dir / name).write_text("", encoding="utf-8")
    for doc_id in document_ids:
        (chunks_dir / f"{doc_id}.jsonl").write_text("", encoding="utf-8")
    return data_dir


def _fake_hit(chunk_id: str, document_id: str, article_no: str = "第一条") -> dict[str, Any]:
    path = f"《测试法规》{article_no}"
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "title": "测试法规",
        "path": path,
        "text": "示例文本",
        "article_no": article_no,
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


def _fake_answer_client(answer: dict[str, Any] | None = None):
    if answer is None:
        answer = {
            "conclusion": "结论。",
            "citations": ["《测试法规》第一条"],
            "scope": "",
            "uncertainty": "",
        }

    class FakeClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            return answer

    return FakeClient()


def _fake_judge_client(
    context_relevancy: float = 1.0,
    faithfulness: float = 1.0,
    answer_relevance: float = 1.0,
    claims_verdict: list[str] | None = None,
):
    if claims_verdict is None:
        claims_verdict = ["supported"]

    class FakeClient:
        model = "doubao-seed-2-1-pro-260628"

        def call(self, messages: list[dict[str, str]], *, response_model: type[Any]) -> Any:
            if response_model.__name__ == "ContextJudgment":
                return response_model(helpful=[True])
            if response_model.__name__ == "FaithfulnessJudgment":
                return response_model(claims_verdict=claims_verdict)
            if response_model.__name__ == "RelevanceJudgment":
                return response_model(relevance_likert=5)
            raise RuntimeError("unexpected response model")

    return FakeClient()


def _run_with_fakes(
    *,
    dataset_path: Path,
    data_dir: Path,
    reports_root: Path,
    hits: list[dict[str, Any]] | None = None,
    answer: dict[str, Any] | None = None,
    claims_verdict: list[str] | None = None,
    config: dict[str, Any] | None = None,
    run_id: str = "run_001",
):
    if hits is None:
        hits = [_fake_hit("chunk_001", "doc_a")]
    return run_evaluation(
        dataset_path=dataset_path,
        run_id=run_id,
        data_dir=data_dir,
        reports_root=reports_root,
        config=config or _make_config(),
        retriever_factory=lambda _dd: _fake_retriever(hits),
        answer_client_factory=lambda _model: _fake_answer_client(answer),
        judge_client_factory=lambda _model: _fake_judge_client(claims_verdict=claims_verdict),
        publisher=publish_run_atomic,
        _git_info_fn=lambda: ("abc1234", False),
        _now_fn=lambda: datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture(autouse=True)
def _env_models(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL", "doubao-1-5-lite-32k-250115")
    monkeypatch.setenv("WS_RAG_JUDGE_MODEL", "doubao-seed-2-1-pro-260628")


def test_load_config_reads_thresholds(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config()), encoding="utf-8")
    config = load_config(config_path)
    assert config["thresholds"]["faithfulness"] == 0.9


def test_preflight_rejects_missing_dataset(tmp_path: Path):
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=tmp_path / "missing.json",
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
        )
    assert exc_info.value.evaluation_error.stage == "preflight"


def test_preflight_rejects_fingerprint_mismatch(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    # Corrupt fingerprint after save.
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    data["dataset_fingerprint"] = "tampered"
    dataset_path.write_text(json.dumps(data), encoding="utf-8")

    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=dataset_path,
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
        )
    assert "fingerprint" in exc_info.value.evaluation_error.message.lower()


def test_preflight_rejects_missing_chunks(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_b"])  # chunk for doc_a missing
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=dataset_path,
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
        )
    assert exc_info.value.evaluation_error.stage_description == "chunk 文件缺失"


def test_preflight_rejects_missing_index_file(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    (data_dir / "index" / "faiss.index").unlink()
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=dataset_path,
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
        )
    assert "faiss.index" in exc_info.value.evaluation_error.message


def test_preflight_rejects_existing_run(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    reports_root = tmp_path / "reports"
    (reports_root / "run_001").mkdir(parents=True)
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=dataset_path,
            data_dir=data_dir,
            reports_root=reports_root,
        )
    assert exc_info.value.evaluation_error.stage == "preflight"


def test_preflight_rejects_missing_chat_model(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    with pytest.raises(FatalEvaluationError) as exc_info:
        _run_with_fakes(
            dataset_path=dataset_path,
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
        )
    assert "CHAT_MODEL" in exc_info.value.evaluation_error.message


def test_successful_run_publishes_report(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    reports_root = tmp_path / "reports"

    result = _run_with_fakes(
        dataset_path=dataset_path,
        data_dir=data_dir,
        reports_root=reports_root,
    )

    assert result.run_dir is not None
    assert result.run_dir.exists()
    assert (result.run_dir / "report.json").exists()
    assert (result.run_dir / "errors.json").exists()
    assert result.report.run_id == "run_001"
    assert result.report.dataset.dataset_id == "ds_001"
    assert result.report.summary.question_count == 1
    assert result.report.summary.passed_questions == 1
    assert result.errors.errors == []


def test_recoverable_answer_error_continues(tmp_path: Path):
    questions = [
        DatasetQuestion(
            question_id="q_001",
            question="问题1？",
            question_type="frequent",
            answerable=True,
            expected_behavior="answer",
            expected_article="第一条",
            source_chunk_id="chunk_001",
            answer_sketch="摘要1",
        ),
        DatasetQuestion(
            question_id="q_002",
            question="问题2？",
            question_type="boundary",
            answerable=True,
            expected_behavior="answer",
            expected_article="第一条",
            source_chunk_id="chunk_002",
            answer_sketch="摘要2",
        ),
    ]
    dataset = _make_dataset(tmp_path, questions=questions)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    reports_root = tmp_path / "reports"

    call_count = 0

    class FlakyAnswerClient:
        def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            # Fail the first question even after one retry, then succeed on the second question.
            if call_count <= 2:
                raise RuntimeError("temporary model failure")
            return {
                "conclusion": "结论。",
                "citations": ["《测试法规》第一条"],
                "scope": "",
                "uncertainty": "",
            }

    result = run_evaluation(
        dataset_path=dataset_path,
        run_id="run_001",
        data_dir=data_dir,
        reports_root=reports_root,
        config=_make_config(),
        retriever_factory=lambda _dd: _fake_retriever([_fake_hit("chunk_001", "doc_a")]),
        answer_client_factory=lambda _model: FlakyAnswerClient(),
        judge_client_factory=lambda _model: _fake_judge_client(),
        publisher=publish_run_atomic,
        _git_info_fn=lambda: ("abc1234", False),
        _now_fn=lambda: datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.run_dir.exists()
    assert result.report.summary.question_count == 1
    assert result.report.summary.passed_questions == 1
    assert len(result.errors.errors) == 1
    assert result.errors.errors[0].question_id == "q_001"
    assert result.errors.errors[0].recoverable is True


def test_fatal_retrieval_error_aborts(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])

    class BadRetriever:
        def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
            raise RuntimeError("fusion failed")

    with pytest.raises(FatalEvaluationError) as exc_info:
        run_evaluation(
            dataset_path=dataset_path,
            run_id="run_001",
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
            config=_make_config(),
            retriever_factory=lambda _dd: BadRetriever(),
            answer_client_factory=lambda _model: _fake_answer_client(),
            judge_client_factory=lambda _model: _fake_judge_client(),
            publisher=publish_run_atomic,
            _git_info_fn=lambda: ("abc1234", False),
            _now_fn=lambda: datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert exc_info.value.evaluation_error.stage == "fusion"
    assert not (tmp_path / "reports" / "run_001").exists()


def test_fatal_judge_error_aborts(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])

    class FailingJudgeClient:
        model = "doubao-seed-2-1-pro-260628"

        def call(self, messages: list[dict[str, str]], *, response_model: type[Any]) -> Any:
            raise EvalClientError("judge refused")

    with pytest.raises(FatalEvaluationError) as exc_info:
        run_evaluation(
            dataset_path=dataset_path,
            run_id="run_001",
            data_dir=data_dir,
            reports_root=tmp_path / "reports",
            config=_make_config(),
            retriever_factory=lambda _dd: _fake_retriever([_fake_hit("chunk_001", "doc_a")]),
            answer_client_factory=lambda _model: _fake_answer_client(),
            judge_client_factory=lambda _model: FailingJudgeClient(),
            publisher=publish_run_atomic,
            _git_info_fn=lambda: ("abc1234", False),
            _now_fn=lambda: datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert exc_info.value.evaluation_error.stage == "judge"
    assert not (tmp_path / "reports" / "run_001").exists()


def test_run_records_system_and_protocol_identity(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    result = _run_with_fakes(
        dataset_path=dataset_path,
        data_dir=data_dir,
        reports_root=tmp_path / "reports",
    )
    assert result.report.system.git_commit == "abc1234"
    assert result.report.system.git_dirty is False
    assert result.report.protocol.judge_model == "doubao-seed-2-1-pro-260628"
    assert result.report.protocol.answer_model == "doubao-1-5-lite-32k-250115"
    assert result.report.protocol.judge_calibrated is False


def test_corpus_fingerprint_is_stable_and_salt_aware(tmp_path: Path):
    dataset = _make_dataset(tmp_path)
    data_dir = _setup_data_dir(tmp_path, ["doc_a"])
    fp1 = compute_corpus_fingerprint(data_dir, dataset)
    fp2 = compute_corpus_fingerprint(data_dir, dataset)
    assert fp1 == fp2
    assert fp1.startswith("sha256:")

    (data_dir / "index" / "retrieval.db").write_text("changed", encoding="utf-8")
    fp3 = compute_corpus_fingerprint(data_dir, dataset)
    assert fp3 != fp1


def test_real_index_offline_integration(tmp_path: Path):
    index_dir = Path("data/index")
    chunks_dir = Path("data/chunks")
    if not index_dir.exists() or not chunks_dir.exists():
        pytest.skip("真实索引或 chunks 不存在")

    doc_id = "doc_d97773f1500c"
    if not (chunks_dir / f"{doc_id}.jsonl").exists():
        pytest.skip("目标文档 chunk 不存在")

    from app.services.retriever import Retriever

    questions = [
        DatasetQuestion(
            question_id="q_real_001",
            question="消防监督检查规定第十条规定了什么？",
            question_type="frequent",
            answerable=True,
            expected_behavior="answer",
            expected_article="第十条",
            source_chunk_id="chunk_real_001",
            answer_sketch="公安机关消防机构应进行监督检查。",
        )
    ]
    dataset = _make_dataset(tmp_path, questions=questions)
    # Override document id/title to match real document.
    dataset.documents[0].document_id = doc_id
    dataset.documents[0].title = "消防监督检查规定"
    dataset.documents[0].source_sha256 = "real_sha256"
    dataset_path = _persist_dataset(tmp_path, dataset)
    data_dir = _setup_data_dir(tmp_path, [doc_id])
    # Replace empty chunk/index files with real ones for the offline test.
    import shutil

    shutil.copy(chunks_dir / f"{doc_id}.jsonl", data_dir / "chunks" / f"{doc_id}.jsonl")
    for name in ["retrieval.db", "faiss.index", "vector_map.json"]:
        src = index_dir / name
        if src.exists():
            shutil.copy(src, data_dir / "index" / name)

    answer = {
        "conclusion": "根据第十条，公安机关消防机构应当对机关、团体、企业、事业等单位遵守消防法律、法规的情况依法进行监督检查。",
        "citations": ["《消防监督检查规定》第十条"],
        "scope": "",
        "uncertainty": "",
    }

    result = run_evaluation(
        dataset_path=dataset_path,
        run_id="run_real_001",
        data_dir=data_dir,
        reports_root=tmp_path / "reports",
        config=_make_config(),
        retriever_factory=lambda dd: Retriever.from_disk(
            keyword_db_path=dd / "index" / "retrieval.db",
            vector_index_path=dd / "index" / "faiss.index",
            vector_map_path=dd / "index" / "vector_map.json",
        ),
        answer_client_factory=lambda _model: _fake_answer_client(answer),
        judge_client_factory=lambda _model: _fake_judge_client(),
        publisher=publish_run_atomic,
        _git_info_fn=lambda: ("abc1234", False),
        _now_fn=lambda: datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.run_dir.exists()
    assert result.report.summary.question_count == 1
    assert len(result.report.documents[0].questions[0].retrieved_chunks) > 0
