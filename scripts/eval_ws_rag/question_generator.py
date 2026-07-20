from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.eval_ws_rag.dataset_models import DatasetQuestion

LOGGER = logging.getLogger(__name__)


class CompleteFn(Protocol):
    def __call__(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]: ...


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    question_type: str
    answerable: bool
    expected_behavior: str
    expected_article: str | None = None
    source_chunk_id: str
    answer_sketch: str


class QuestionGenerationError(RuntimeError):
    """Raised when question generation fails or violates local gates."""


@dataclass
class QuestionGeneratorClient:
    complete: CompleteFn
    model: str = "deepseek-v4-pro-260425"
    prompt_version: str = "qg_v1"
    max_retries: int = 1
    retry_backoff_seconds: float = 2.0
    sleep_fn: Callable[[float], None] = time.sleep

    def generate(
        self,
        *,
        chunks: Sequence[dict[str, Any]],
        document_id: str,
        question_type: str,
        count: int,
        seed: int,
    ) -> list[GeneratedQuestion]:
        if count <= 0:
            return []

        messages = _build_messages(
            chunks=chunks,
            document_id=document_id,
            question_type=question_type,
            count=count,
            seed=seed,
            prompt_version=self.prompt_version,
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.complete(messages)
                break
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self.sleep_fn(self.retry_backoff_seconds * (attempt + 1))
                    continue
                raise QuestionGenerationError(
                    f"question generation failed for {document_id}/{question_type}: {exc}"
                ) from exc
        else:
            if last_error is not None:
                raise QuestionGenerationError(
                    f"question generation failed for {document_id}/{question_type}: {last_error}"
                ) from last_error
            raise QuestionGenerationError(
                f"question generation failed for {document_id}/{question_type}"
            )

        questions_data = response.get("questions") if isinstance(response, dict) else None
        if not isinstance(questions_data, list):
            raise QuestionGenerationError(
                f"expected response['questions'] list, got {type(questions_data).__name__}"
            )

        questions: list[GeneratedQuestion] = []
        for item in questions_data:
            try:
                questions.append(GeneratedQuestion.model_validate(item))
            except ValidationError as exc:
                raise QuestionGenerationError(
                    f"generated question schema invalid: {exc}"
                ) from exc
        return questions


def _build_messages(
    *,
    chunks: Sequence[dict[str, Any]],
    document_id: str,
    question_type: str,
    count: int,
    seed: int,
    prompt_version: str,
) -> list[dict[str, str]]:
    system_prompt = (
        "你是消防法规评测问题生成器。"
        "请根据给定的法规条文片段，生成指定类型和数量的评测问题。"
        "只输出一个 JSON object，首字符必须是 {，末字符必须是 }。"
        "不要 Markdown，不要代码块，不要解释。"
        "JSON object 必须包含一个名为 questions 的数组，每个元素包含："
        "question（string）、question_type（string）、answerable（boolean）、"
        "expected_behavior（'answer' 或 'refuse'）、expected_article（string 或 null）、"
        "source_chunk_id（string）、answer_sketch（string）。"
        "可回答问题必须基于文件中真实存在的条文；不可回答问题对应文件中不存在的条文或无法回答的场景，expected_article 必须为 null。"
    )

    chunk_lines = []
    for chunk in chunks:
        chunk_lines.append(
            f"- chunk_id: {chunk.get('chunk_id')}\n"
            f"  article_no: {chunk.get('article_no')}\n"
            f"  text: {chunk.get('text', '')[:500]}"
        )

    user_prompt = (
        f"document_id: {document_id}\n"
        f"question_type: {question_type}\n"
        f"count: {count}\n"
        f"seed: {seed}\n"
        f"prompt_version: {prompt_version}\n"
        f"chunks:\n" + "\n".join(chunk_lines)
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_document_questions(
    *,
    client: QuestionGeneratorClient,
    chunks: Sequence[dict[str, Any]],
    document_id: str,
    counts: dict[str, int],
    seed: int,
    start_index: int = 1,
) -> list[Any]:
    """Generate validated questions for one document across all configured types.

    Returns a list of dicts ready to become DatasetQuestion instances.

    ``start_index`` 是 dataset 级连续编号的起始值，调用方负责跨文档递增，
    以保证 question_id 在整个 dataset 内唯一（数据契约第 10 条）。
    """
    article_nos = {str(c.get("article_no")) for c in chunks if c.get("article_no")}
    chunk_ids = {str(c.get("chunk_id")) for c in chunks if c.get("chunk_id")}

    generated: list[GeneratedQuestion] = []
    for question_type in ("frequent", "boundary", "diversity"):
        count = counts.get(question_type, 0)
        if count <= 0:
            continue
        batch = client.generate(
            chunks=chunks,
            document_id=document_id,
            question_type=question_type,
            count=count,
            seed=seed,
        )
        generated.extend(batch)

    seen_questions: set[str] = set()
    questions: list[dict[str, Any]] = []
    next_index = start_index
    for gq in generated:
        normalized = gq.question.strip()
        if not normalized:
            raise QuestionGenerationError("generated question text is empty")
        if normalized.lower() in seen_questions:
            continue
        seen_questions.add(normalized.lower())

        if gq.answerable:
            if not gq.expected_article:
                raise QuestionGenerationError(
                    f"answerable question missing expected_article: {gq.question}"
                )
            if gq.expected_article not in article_nos:
                raise QuestionGenerationError(
                    f"expected_article {gq.expected_article} not found in document chunks"
                )
        else:
            if gq.expected_behavior != "refuse":
                raise QuestionGenerationError(
                    f"unanswerable question must have expected_behavior=refuse: {gq.question}"
                )
            if gq.expected_article is not None:
                raise QuestionGenerationError(
                    f"boundary question must not have expected_article: {gq.question}"
                )

        if gq.source_chunk_id not in chunk_ids:
            raise QuestionGenerationError(
                f"source_chunk_id {gq.source_chunk_id} not found in document chunks"
            )

        questions.append(
            DatasetQuestion(
                question_id=f"q_{gq.question_type}_{next_index:03d}",
                question=gq.question,
                question_type=gq.question_type,
                answerable=gq.answerable,
                expected_behavior=gq.expected_behavior,
                expected_article=gq.expected_article,
                source_chunk_id=gq.source_chunk_id,
                answer_sketch=gq.answer_sketch,
            )
        )
        next_index += 1
    return questions


def build_question_generator_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    max_retries: int | None = None,
) -> QuestionGeneratorClient:
    """Build client from explicit values or environment variables."""
    from openai import OpenAI

    final_api_key = api_key or os.environ.get("WS_RAG_QUESTION_GENERATOR_API_KEY", "")
    final_base_url = base_url or os.environ.get("WS_RAG_QUESTION_GENERATOR_BASE_URL", "")
    final_model = model or os.environ.get("WS_RAG_QUESTION_GENERATOR_MODEL", "deepseek-v4-pro-260425")
    final_max_retries = max_retries if max_retries is not None else int(
        os.environ.get("WS_RAG_MODEL_MAX_RETRIES", "1")
    )

    client = OpenAI(api_key=final_api_key, base_url=final_base_url)

    def complete(messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        response = client.chat.completions.create(
            model=final_model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_questions",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": GeneratedQuestion.model_json_schema(),
                            }
                        },
                        "required": ["questions"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        content = response.choices[0].message.content
        if isinstance(content, dict):
            return content
        return json.loads(content)

    return QuestionGeneratorClient(
        complete=complete,
        model=final_model,
        max_retries=final_max_retries,
    )
