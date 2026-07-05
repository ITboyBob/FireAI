from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval_ws_rag.runtime_config import RuntimeConfig, load_runtime_config


def _base_config() -> dict:
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
        "default_judge_repetitions": 3,
        "default_judge_temperature": 0,
        "default_max_retries": 1,
        "default_concurrency": 1,
    }


@pytest.fixture(autouse=True)
def _env_models(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL", "doubao-1-5-lite-32k-250115")
    monkeypatch.setenv("WS_RAG_JUDGE_MODEL", "doubao-seed-2-1-pro-260628")


def test_loads_answer_model_from_chat_env():
    config = load_runtime_config(_base_config())
    assert config.answer_model == "doubao-1-5-lite-32k-250115"


def test_loads_judge_model_from_ws_rag_env():
    config = load_runtime_config(_base_config())
    assert config.judge_model == "doubao-seed-2-1-pro-260628"


def test_loads_question_generator_defaults():
    config = load_runtime_config(_base_config())
    assert config.question_generator_model == "deepseek-v4-pro-260425"


def test_question_counts_default_to_one():
    config = load_runtime_config(_base_config())
    assert config.frequent_questions_per_document == 1
    assert config.boundary_questions_per_document == 1
    assert config.diversity_questions_per_document == 1


def test_model_concurrency_and_retries_default_to_one():
    config = load_runtime_config(_base_config())
    assert config.model_concurrency == 1
    assert config.model_max_retries == 1


def test_judge_temperature_is_zero():
    config = load_runtime_config(_base_config())
    assert config.judge_temperature == 0.0


def test_judge_calibrated_is_false_and_rejected():
    config = load_runtime_config(_base_config())
    assert config.judge_calibrated is False

    with pytest.raises(ValueError, match="judge_calibrated"):
        RuntimeConfig(
            answer_model="a",
            judge_model="j",
            judge_calibrated=True,
            thresholds=_base_config()["thresholds"],
        )


def test_summary_excludes_api_keys():
    monkeypatch = pytest.MonkeyPatch()
    with monkeypatch.context() as m:
        m.setenv("CHAT_API_KEY", "secret-chat")
        m.setenv("WS_RAG_JUDGE_API_KEY", "secret-judge")
        m.setenv("WS_RAG_QUESTION_GENERATOR_API_KEY", "secret-qg")
        config = load_runtime_config(_base_config())
        summary = config.non_secret_summary()
        assert "answer_api_key" not in summary
        assert "judge_api_key" not in summary
        assert "question_generator_api_key" not in summary
        assert summary["answer_model"] == "doubao-1-5-lite-32k-250115"
        assert summary["judge_model"] == "doubao-seed-2-1-pro-260628"


def test_missing_answer_model_raises(monkeypatch):
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    with pytest.raises(ValueError):
        load_runtime_config(_base_config())


def test_missing_judge_model_raises(monkeypatch):
    monkeypatch.delenv("WS_RAG_JUDGE_MODEL", raising=False)
    with pytest.raises(ValueError):
        load_runtime_config(_base_config())


def test_question_count_env_overrides():
    import os

    os.environ["WS_RAG_FREQUENT_QUESTIONS_PER_DOCUMENT"] = "2"
    os.environ["WS_RAG_BOUNDARY_QUESTIONS_PER_DOCUMENT"] = "3"
    os.environ["WS_RAG_DIVERSITY_QUESTIONS_PER_DOCUMENT"] = "4"
    try:
        config = load_runtime_config(_base_config())
        assert config.frequent_questions_per_document == 2
        assert config.boundary_questions_per_document == 3
        assert config.diversity_questions_per_document == 4
    finally:
        del os.environ["WS_RAG_FREQUENT_QUESTIONS_PER_DOCUMENT"]
        del os.environ["WS_RAG_BOUNDARY_QUESTIONS_PER_DOCUMENT"]
        del os.environ["WS_RAG_DIVERSITY_QUESTIONS_PER_DOCUMENT"]


def test_loads_from_config_file(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_base_config()), encoding="utf-8")
    config = load_runtime_config(config_path)
    assert config.top_k == 5
    assert config.thresholds["faithfulness"] == 0.9
