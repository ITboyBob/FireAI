from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class CompleteFn(Protocol):
    def __call__(self, messages: Sequence[dict[str, str]], response_model: type[T]) -> T: ...


class ContextJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    helpful: list[bool]


class FaithfulnessJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims_verdict: list[str]


class RelevanceJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance_likert: int = Field(..., ge=1, le=5)


class EvalClientError(RuntimeError):
    """Raised when the structured evaluation client cannot produce a valid response."""


@dataclass
class StructuredEvalClient:
    complete: CompleteFn
    model: str = "doubao-seed-2-1-pro-260628"
    max_retries: int = 1
    retry_backoff_seconds: float = 2.0
    sleep_fn: Callable[[float], None] = time.sleep

    def call(
        self,
        messages: Sequence[dict[str, str]],
        *,
        response_model: type[T],
    ) -> T:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.complete(messages, response_model)
                return response_model.model_validate(raw)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries and _is_retryable(exc):
                    self.sleep_fn(self.retry_backoff_seconds * (attempt + 1))
                    continue
                break

        message = str(last_error) if last_error else "unknown evaluation client failure"
        raise EvalClientError(message) from last_error


def _is_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate limit" in text or "429" in text or "timeout" in text or "connection" in text or "temporary" in text


def build_judge_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
) -> StructuredEvalClient:
    """Build a structured evaluation client from environment variables."""
    from openai import OpenAI

    final_api_key = api_key or os.environ.get("WS_RAG_JUDGE_API_KEY", "")
    final_base_url = base_url or os.environ.get("WS_RAG_JUDGE_BASE_URL", "")
    final_model = model or os.environ.get("WS_RAG_JUDGE_MODEL", "doubao-seed-2-1-pro-260628")
    final_temperature = 0.0 if temperature is None else temperature
    final_max_retries = max_retries if max_retries is not None else int(
        os.environ.get("WS_RAG_MODEL_MAX_RETRIES", "1")
    )

    client = OpenAI(api_key=final_api_key, base_url=final_base_url)

    def complete(messages: Sequence[dict[str, str]], response_model: type[T]) -> T:
        response = client.chat.completions.create(
            model=final_model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=final_temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        )
        content = response.choices[0].message.content
        if isinstance(content, dict):
            data = content
        else:
            data = json.loads(content)
        return response_model.model_validate(data)

    return StructuredEvalClient(
        complete=complete,
        model=final_model,
        max_retries=final_max_retries,
    )
