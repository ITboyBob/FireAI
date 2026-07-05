from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SCHEMA_MAJOR = 1
_SUPPORTED_MINORS = {0, 1}


def _check_schema_version(value: str) -> str:
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"schema_version must be semver: {value}")
    major = int(parts[0])
    minor = int(parts[1])
    if major != _SCHEMA_MAJOR:
        raise ValueError(f"unsupported major schema version: {major}")
    if minor not in _SUPPORTED_MINORS:
        raise ValueError(f"unsupported minor schema version: {minor}")
    return value


class MetricScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_relevancy: float = Field(..., ge=0.0, le=1.0)
    source_coverage: float = Field(..., ge=0.0, le=1.0)
    faithfulness: float = Field(..., ge=0.0, le=1.0)
    answer_relevance: float = Field(..., ge=0.0, le=1.0)
    citation_validity: float = Field(..., ge=0.0, le=1.0)
    refusal_appropriateness: float = Field(..., ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {
            "context_relevancy": self.context_relevancy,
            "source_coverage": self.source_coverage,
            "faithfulness": self.faithfulness,
            "answer_relevance": self.answer_relevance,
            "citation_validity": self.citation_validity,
            "refusal_appropriateness": self.refusal_appropriateness,
        }


class FailureReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    description: str


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    path: str
    text: str
    retrieval_score: float
    keyword_score: float
    vector_score: float
    sources: list[str]
    cited: bool = False


class CitationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    path: str
    text: str
    matched_chunk_id: str
    citation_label: str


class JudgeDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repetition: int = Field(..., ge=1)
    context_helpful: list[bool] | None = None
    claims_verdict: list[dict[str, Any]] | None = None
    answer_relevance_likert: int | None = Field(None, ge=1, le=5)


class JudgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_relevancy: float = Field(..., ge=0.0, le=1.0)
    faithfulness: float = Field(..., ge=0.0, le=1.0)
    answer_relevance: float = Field(..., ge=0.0, le=1.0)
    details: list[JudgeDetail]
    prompt_version: str
    model: str


class QuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    question_type: str
    answerable: bool
    expected_behavior: str
    expected_article: str | None = None
    source_chunk_id: str
    retrieved_chunks: list[RetrievedChunk]
    answer: str
    citations: list[CitationRecord]
    refused: bool
    uncertainty: str | None = None
    metrics: MetricScores
    red_line_failures: list[FailureReason]
    failure_reasons: list[FailureReason]
    judge_result: JudgeResult | None = None
    passed: bool


class DocumentScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    source_sha256: str | None = None
    content_class: str | None = None
    question_count: int = Field(..., ge=0)
    passed_questions: int | None = Field(None, ge=0)
    failed_questions_count: int | None = Field(None, ge=0)
    red_line_failures_count: int | None = Field(None, ge=0)
    metrics: MetricScores
    overall_pass_rate: float = Field(..., ge=0.0, le=1.0)
    failed_questions: list[str]
    questions: list[QuestionResult]


class DatasetIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_fingerprint: str
    document_ids: list[str]


class EvaluationProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    protocol_fingerprint: str
    judge_model: str
    judge_prompt_version: str
    judge_temperature: float = 0.0
    judge_repetitions: int = Field(..., ge=1)
    judge_calibrated: bool
    evidence_order_strategy: str
    metric_algorithm_version: str
    thresholds: MetricScores
    answer_model: str
    answer_prompt_version: str
    top_k: int = Field(..., ge=1)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)

    @field_validator("judge_calibrated")
    @classmethod
    def _judge_must_be_uncalibrated(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("judge_calibrated must be false in this implementation")
        return value

    @staticmethod
    def default_thresholds() -> dict[str, float]:
        return {
            "context_relevancy": 0.8,
            "source_coverage": 0.9,
            "faithfulness": 0.9,
            "answer_relevance": 0.8,
            "citation_validity": 1.0,
            "refusal_appropriateness": 0.9,
        }

    @model_validator(mode="after")
    def _protocol_fingerprint_covers_key_fields(self) -> "EvaluationProtocol":
        expected = compute_protocol_fingerprint(
            judge_model=self.judge_model,
            judge_prompt_version=self.judge_prompt_version,
            judge_repetitions=self.judge_repetitions,
            evidence_order_strategy=self.evidence_order_strategy,
            metric_algorithm_version=self.metric_algorithm_version,
            thresholds=self.thresholds.as_dict(),
        )
        if self.protocol_fingerprint != expected:
            raise ValueError("protocol_fingerprint does not cover required fields")
        return self


class EvaluatedSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    git_commit: str
    git_dirty: bool
    corpus_fingerprint: str


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    run_id: str
    created_at: datetime
    dataset: DatasetIdentity
    protocol: EvaluationProtocol
    system: EvaluatedSystem
    summary: DocumentScorecard
    documents: list[DocumentScorecard]

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)

    @model_validator(mode="after")
    def _summary_consistency(self) -> "EvaluationReport":
        total = sum(doc.question_count for doc in self.documents)
        if self.summary.question_count != total:
            raise ValueError(
                f"summary.question_count ({self.summary.question_count}) does not match "
                f"sum of document question counts ({total})"
            )

        all_questions: list[QuestionResult] = []
        for doc in self.documents:
            all_questions.extend(doc.questions)
            if len(doc.questions) != doc.question_count:
                raise ValueError(
                    f"document {doc.document_id}: question_count ({doc.question_count}) does not match "
                    f"questions length ({len(doc.questions)})"
                )

        passed = sum(1 for q in all_questions if q.passed)
        failed = len(all_questions) - passed
        red_lines = sum(len(q.red_line_failures) for q in all_questions)

        if getattr(self.summary, "passed_questions", None) is not None:
            if self.summary.passed_questions != passed:
                raise ValueError(
                    f"summary.passed_questions ({self.summary.passed_questions}) does not match {passed}"
                )
        if getattr(self.summary, "failed_questions_count", None) is not None:
            if self.summary.failed_questions_count != failed:
                raise ValueError(
                    f"summary.failed_questions_count ({self.summary.failed_questions_count}) does not match {failed}"
                )
        if getattr(self.summary, "red_line_failures_count", None) is not None:
            if self.summary.red_line_failures_count != red_lines:
                raise ValueError(
                    f"summary.red_line_failures_count ({self.summary.red_line_failures_count}) does not match {red_lines}"
                )
        return self


class EvaluationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str | None = None
    question_id: str | None = None
    stage: str
    stage_description: str
    error_type: str
    message: str
    recoverable: bool
    input_snapshot: dict[str, Any] | None = None


class ErrorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    run_id: str
    created_at: datetime
    errors: list[EvaluationError]

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)


def compute_protocol_fingerprint(
    *,
    judge_model: str,
    judge_prompt_version: str,
    judge_repetitions: int,
    evidence_order_strategy: str,
    metric_algorithm_version: str,
    thresholds: dict[str, float],
) -> str:
    """Return a deterministic canonical fingerprint covering protocol fields."""
    # Use single quotes inside the canonical string so it can be embedded in JSON without escaping.
    thresholds_text = json.dumps(thresholds, sort_keys=True, ensure_ascii=False).replace('"', "'")
    canonical = (
        f"judge={judge_model}|"
        f"judge_prompt={judge_prompt_version}|"
        f"reps={judge_repetitions}|"
        f"order={evidence_order_strategy}|"
        f"metric={metric_algorithm_version}|"
        f"thresholds={thresholds_text}"
    )
    digest = _compute_fingerprint(canonical)
    return f"{canonical}|sha256={digest}"


def _compute_fingerprint(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
