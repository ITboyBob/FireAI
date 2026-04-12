from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import json
import re
import time
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.chat import ModelAnswer


class ChatCompletionError(RuntimeError):
    """Raised when the chat client cannot produce a valid structured answer."""


@dataclass
class OpenAIChatClient:
    api_key: str
    base_url: str
    model: str
    timeout: float = 30.0
    temperature: float = 0.0
    client_factory: Callable[..., Any] = OpenAI
    max_retries: int = 1
    retry_backoff_seconds: float = 2.0
    sleep_fn: Callable[[float], None] = time.sleep
    _client: Any | None = field(default=None, init=False, repr=False)

    def complete(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        if not messages:
            raise ValueError("messages must not be empty")

        last_error: ChatCompletionError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._get_client().chat.completions.create(
                    model=self.model,
                    messages=[{"role": item["role"], "content": item["content"]} for item in messages],
                    temperature=self.temperature,
                    response_format=_build_response_format(self.base_url),
                )
                payload = _normalize_json_payload(_extract_message_payload(response))
                return ModelAnswer.model_validate_json(payload).model_dump(mode="json")
            except ValidationError as exc:
                raise ChatCompletionError("模型返回了无法通过 schema 校验的 JSON。") from exc
            except ChatCompletionError as exc:
                last_error = exc
                if attempt < self.max_retries and _is_retryable_provider_error(str(exc)):
                    self.sleep_fn(self.retry_backoff_seconds * (attempt + 1))
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise ChatCompletionError("模型调用失败。")

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self.client_factory(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client


def _extract_message_payload(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        provider_error = _extract_provider_error(response)
        if provider_error:
            raise ChatCompletionError(provider_error)
        raise ChatCompletionError("模型响应中缺少 choices。")

    message = getattr(choices[0], "message", None)
    if message is None and isinstance(choices[0], dict):
        message = choices[0].get("message")
    if message is None:
        raise ChatCompletionError("模型响应中缺少 message。")

    refusal = _read_value(message, "refusal")
    if refusal:
        raise ChatCompletionError(f"模型拒绝响应：{refusal}")

    content = _read_value(message, "content")
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, str):
        text = content.strip()
        if not text:
            raise ChatCompletionError("模型响应缺少 JSON 内容。")
        return text
    if isinstance(content, Sequence):
        text = "".join(_extract_content_part(part) for part in content).strip()
        if not text:
            raise ChatCompletionError("模型响应缺少 JSON 内容。")
        return text
    raise ChatCompletionError("模型响应内容不是可解析的 JSON 文本。")


def _build_response_format(base_url: str) -> dict[str, Any]:
    if "iflow.cn" in base_url.lower():
        return {"type": "text"}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "chat_answer",
            "strict": True,
            "schema": ModelAnswer.model_json_schema(),
        },
    }


def _read_value(container: Any, key: str) -> Any:
    if isinstance(container, dict):
        return container.get(key)
    return getattr(container, key, None)


def _extract_content_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        if isinstance(part.get("text"), str):
            return part["text"]
        if part.get("type") == "output_text" and isinstance(part.get("text"), str):
            return part["text"]
        return ""

    text = getattr(part, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _extract_provider_error(response: Any) -> str:
    message = _read_value(response, "msg") or _read_value(response, "message")
    status = _read_value(response, "status")
    if not message:
        return ""

    message_text = str(message).strip()
    status_text = str(status).strip() if status is not None else ""
    if not message_text:
        return ""
    if status_text:
        return f"提供商返回错误（status={status_text}）：{message_text}"
    return message_text


def _normalize_json_payload(payload: str) -> str:
    text = payload.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1].strip()
    return text


def _is_retryable_provider_error(message: str) -> bool:
    lowered = message.lower()
    return "rate limit" in lowered or "status=429" in lowered or "status=449" in lowered
