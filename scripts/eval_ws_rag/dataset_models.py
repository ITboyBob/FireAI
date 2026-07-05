from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scripts.eval_ws_rag.report_models import _check_schema_version


class DatasetQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    question_type: str
    answerable: bool
    expected_behavior: str
    expected_article: str | None = None
    source_chunk_id: str
    answer_sketch: str


class DatasetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    source_sha256: str
    content_class: str
    source_summary: str = ""
    questions: list[DatasetQuestion]


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    dataset_id: str
    dataset_fingerprint: str
    created_at: datetime
    generator_model: str
    generator_prompt_version: str
    generation_seed: int
    documents: list[DatasetDocument]

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        return _check_schema_version(value)

    @field_validator("dataset_fingerprint")
    @classmethod
    def _fingerprint_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("dataset_fingerprint must not be empty")
        return value

    def canonical_payload(self) -> str:
        """Return deterministic canonical JSON text used for fingerprinting."""
        return canonical_dataset_payload(self)

    def compute_fingerprint(self) -> str:
        """Compute SHA-256 fingerprint of the canonical dataset content."""
        return compute_dataset_fingerprint(self.canonical_payload())


def canonical_dataset_payload(dataset: EvaluationDataset) -> str:
    """Serialize dataset to a deterministic canonical form excluding created_at."""
    data = dataset.model_dump(mode="json")
    data.pop("created_at", None)
    data.pop("dataset_fingerprint", None)
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_dataset_fingerprint(payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
