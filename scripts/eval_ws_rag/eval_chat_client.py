from __future__ import annotations

import json
import logging
import os
import re
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


def _provider_prefers_text_json(base_url: str) -> bool:
    """判断 provider 是否对 json_schema 支持不稳定，需要回退到 text JSON 解析。"""
    lower = base_url.lower()
    return "iflow.cn" in lower or "volces.com" in lower


def _extract_json_object(content: str) -> dict[str, Any]:
    """从模型文本响应中提取第一个 JSON object。

    兼容纯 JSON、Markdown 代码块以及前后带说明文字的情况。
    """
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("响应中未找到 JSON object")
    return json.loads(text[start : end + 1])


def build_judge_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
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
    final_timeout = (
        timeout
        if timeout is not None
        else float(os.environ.get("WS_RAG_JUDGE_TIMEOUT_SECONDS", "60"))
    )

    use_text_json = _provider_prefers_text_json(final_base_url)
    client = OpenAI(api_key=final_api_key, base_url=final_base_url, timeout=final_timeout)

    def complete(messages: Sequence[dict[str, str]], response_model: type[T]) -> T:
        response_format: dict[str, Any]
        if use_text_json:
            response_format = {"type": "text"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            }
        response = client.chat.completions.create(
            model=final_model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=final_temperature,
            response_format=response_format,
            timeout=final_timeout,
        )
        content = response.choices[0].message.content
        if isinstance(content, dict):
            data = content
        elif use_text_json:
            data = _extract_json_object(content)
        else:
            data = json.loads(content)
        return response_model.model_validate(data)

    return StructuredEvalClient(
        complete=complete,
        model=final_model,
        max_retries=final_max_retries,
    )
