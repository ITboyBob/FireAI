from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuntimeConfig(BaseModel):
    """Read-only runtime configuration for the W-S RAG evaluation pipeline.

    All values are loaded from environment variables and the shared JSON config
    file. API keys are retained for runtime use but must never appear in logs or
    published reports.
    """

    model_config = ConfigDict(extra="forbid")

    # Answer generation model (reuses the production chat model env vars).
    answer_model: str
    answer_api_key: str = ""
    answer_base_url: str = ""
    answer_timeout_seconds: float = Field(default=30.0, ge=1.0)
    answer_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Independent LLM Judge model.
    judge_model: str
    judge_api_key: str = ""
    judge_base_url: str = ""
    judge_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    judge_repetitions: int = Field(default=3, ge=1)
    judge_calibrated: bool = False

    # Question generator model (only used by dataset generation).
    question_generator_model: str = "deepseek-v4-pro-260425"
    question_generator_api_key: str = ""
    question_generator_base_url: str = ""

    # Question counts and concurrency controls.
    frequent_questions_per_document: int = Field(default=1, ge=0)
    boundary_questions_per_document: int = Field(default=1, ge=0)
    diversity_questions_per_document: int = Field(default=1, ge=0)
    model_max_retries: int = Field(default=1, ge=0)
    model_concurrency: int = Field(default=1, ge=1)

    # Retrieval/evaluation parameters.
    top_k: int = Field(default=5, ge=1)
    thresholds: dict[str, float]

    @field_validator("judge_calibrated")
    @classmethod
    def _judge_must_be_uncalibrated(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("judge_calibrated must be false in this implementation")
        return value

    @field_validator("answer_model", "judge_model", "question_generator_model")
    @classmethod
    def _model_id_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("model id must not be empty")
        return stripped

    def non_secret_summary(self) -> dict[str, Any]:
        """Return a config dict safe for logging and CLI display."""
        data = self.model_dump(mode="json")
        return {
            key: value
            for key, value in data.items()
            if "api_key" not in key.lower()
        }


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"environment variable {name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"environment variable {name} must be a number") from exc


def load_runtime_config(config: dict[str, Any] | Path) -> RuntimeConfig:
    """Build a RuntimeConfig from environment variables and the JSON config file."""
    if isinstance(config, Path):
        config = json.loads(config.read_text(encoding="utf-8"))

    thresholds = config.get("thresholds", {})
    if not thresholds:
        raise ValueError("config thresholds must not be empty")

    return RuntimeConfig(
        answer_model=os.environ.get("CHAT_MODEL", ""),
        answer_api_key=os.environ.get("CHAT_API_KEY", ""),
        answer_base_url=os.environ.get("CHAT_BASE_URL", ""),
        answer_timeout_seconds=_float_env("CHAT_TIMEOUT_SECONDS", 30.0),
        answer_temperature=_float_env("CHAT_TEMPERATURE", 0.0),
        judge_model=os.environ.get("WS_RAG_JUDGE_MODEL", ""),
        judge_api_key=os.environ.get("WS_RAG_JUDGE_API_KEY", ""),
        judge_base_url=os.environ.get("WS_RAG_JUDGE_BASE_URL", ""),
        judge_temperature=float(config.get("default_judge_temperature", 0)),
        judge_repetitions=int(config.get("default_judge_repetitions", 3)),
        judge_calibrated=False,
        question_generator_model=os.environ.get(
            "WS_RAG_QUESTION_GENERATOR_MODEL", "deepseek-v4-pro-260425"
        ),
        question_generator_api_key=os.environ.get("WS_RAG_QUESTION_GENERATOR_API_KEY", ""),
        question_generator_base_url=os.environ.get("WS_RAG_QUESTION_GENERATOR_BASE_URL", ""),
        frequent_questions_per_document=_int_env("WS_RAG_FREQUENT_QUESTIONS_PER_DOCUMENT", 1),
        boundary_questions_per_document=_int_env("WS_RAG_BOUNDARY_QUESTIONS_PER_DOCUMENT", 1),
        diversity_questions_per_document=_int_env("WS_RAG_DIVERSITY_QUESTIONS_PER_DOCUMENT", 1),
        model_max_retries=_int_env("WS_RAG_MODEL_MAX_RETRIES", int(config.get("default_max_retries", 1))),
        model_concurrency=_int_env("WS_RAG_MODEL_CONCURRENCY", int(config.get("default_concurrency", 1))),
        top_k=int(config.get("default_top_k", 5)),
        thresholds=thresholds,
    )
