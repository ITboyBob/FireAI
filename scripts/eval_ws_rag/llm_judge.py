from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from scripts.eval_ws_rag.eval_chat_client import (
    ContextJudgment,
    EvalClientError,
    FaithfulnessJudgment,
    RelevanceJudgment,
    StructuredEvalClient,
)


@dataclass
class JudgeDetail:
    repetition: int
    context_helpful: list[bool] | None = None
    claims_verdict: list[str] | None = None
    answer_relevance_likert: int | None = None


@dataclass
class JudgeResult:
    context_relevancy: float
    faithfulness: float
    answer_relevance: float
    details: list[JudgeDetail]
    prompt_version: str
    model: str


class JudgeError(RuntimeError):
    """Raised when LLM Judge fails or returns invalid scoring."""


JUDGE_PROMPT_VERSION = "judge_v1"


def score_question(
    *,
    client: StructuredEvalClient,
    question: str,
    answer: str,
    chunks: Sequence[dict[str, Any]],
    repetitions: int,
    seed: int,
    question_id: str,
) -> JudgeResult:
    """Score one question using an independent LLM Judge.

    The Judge is called serially for each metric and each repetition. Evidence
    order is shuffled per repetition using a deterministic seed to counter
    position bias.
    """
    if repetitions < 1:
        raise JudgeError("repetitions must be >= 1")

    details: list[JudgeDetail] = []
    context_scores: list[float] = []
    faithfulness_scores: list[float] = []
    relevance_scores: list[float] = []

    for repetition in range(1, repetitions + 1):
        shuffled = _shuffle_chunks(chunks, seed=seed, question_id=question_id, repetition=repetition)

        try:
            context = client.call(
                _build_context_messages(question, shuffled),
                response_model=ContextJudgment,
            )
            helpful_count = sum(context.helpful)
            context_scores.append(helpful_count / len(context.helpful) if context.helpful else 0.0)

            claims = _split_claims(answer)
            faithfulness = client.call(
                _build_faithfulness_messages(question, answer, shuffled, claims),
                response_model=FaithfulnessJudgment,
            )
            supported = sum(1 for v in faithfulness.claims_verdict if v == "supported")
            faithfulness_scores.append(
                supported / len(faithfulness.claims_verdict) if faithfulness.claims_verdict else 0.0
            )

            relevance = client.call(
                _build_relevance_messages(question, answer),
                response_model=RelevanceJudgment,
            )
            relevance_scores.append(relevance.relevance_likert / 5.0)
        except EvalClientError as exc:
            raise JudgeError(f"Judge failed for {question_id} repetition {repetition}: {exc}") from exc

        details.append(
            JudgeDetail(
                repetition=repetition,
                context_helpful=context.helpful,
                claims_verdict=faithfulness.claims_verdict,
                answer_relevance_likert=relevance.relevance_likert,
            )
        )

    return JudgeResult(
        context_relevancy=sum(context_scores) / len(context_scores) if context_scores else 0.0,
        faithfulness=sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0,
        answer_relevance=sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0,
        details=details,
        prompt_version=JUDGE_PROMPT_VERSION,
        model=client.model,
    )


def _shuffle_chunks(
    chunks: Sequence[dict[str, Any]], *, seed: int, question_id: str, repetition: int
) -> list[dict[str, Any]]:
    rng = random.Random(f"{seed}|{question_id}|{repetition}")
    shuffled = list(chunks)
    rng.shuffle(shuffled)
    return shuffled


def _split_claims(answer: str) -> list[str]:
    sentences = re.split(r"[。！？\n]", answer)
    return [s.strip() for s in sentences if s.strip()]


def _build_context_messages(question: str, chunks: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    system = (
        "你是消防法规 RAG 评测中的上下文相关性 Judge。"
        "请判断每个证据片段对回答问题是否有帮助。"
        "只看内容相关性，不看答案长度。"
        "输出 JSON：{\"helpful\": [true/false, ...]}"
    )
    evidence_lines = []
    for chunk in chunks:
        evidence_lines.append(f"- chunk_id: {chunk.get('chunk_id')}\n  text: {chunk.get('text', '')[:500]}")
    user = f"问题：{question}\n\n证据片段：\n" + "\n".join(evidence_lines)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _build_faithfulness_messages(
    question: str,
    answer: str,
    chunks: Sequence[dict[str, Any]],
    claims: Sequence[str],
) -> list[dict[str, str]]:
    system = (
        "你是消防法规 RAG 评测中的忠实度 Judge。"
        "给定问题和证据，判断答案拆成的每个断言是否被证据支持。"
        "只看断言与证据的对应关系，不看答案长度。"
        "输出 JSON：{\"claims_verdict\": [\"supported\"|\"not_supported\"|\"unknown\", ...]}"
    )
    evidence_lines = []
    for chunk in chunks:
        evidence_lines.append(f"- chunk_id: {chunk.get('chunk_id')}\n  text: {chunk.get('text', '')[:500]}")
    claim_lines = "\n".join(f"- {claim}" for claim in claims)
    user = (
        f"问题：{question}\n"
        f"答案：{answer}\n\n"
        "断言列表：\n" + claim_lines + "\n\n"
        "证据片段：\n" + "\n".join(evidence_lines)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _build_relevance_messages(question: str, answer: str) -> list[dict[str, str]]:
    system = (
        "你是消防法规 RAG 评测中的答案相关性 Judge。"
        "判断答案对问题的直接有用程度，1-5 分。"
        "只看是否回应问题，不看答案长度。"
        "输出 JSON：{\"relevance_likert\": 1-5}"
    )
    user = f"问题：{question}\n答案：{answer}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
