from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DocumentLoadError(RuntimeError):
    """Raised when a document cannot be loaded for evaluation."""


@dataclass
class LoadedDocument:
    document_id: str
    title: str
    source_sha256: str
    extraction_class: str
    content_class: str
    chunks: list[dict[str, Any]]


def load_document_chunks(chunks_dir: Path, document_id: str) -> LoadedDocument:
    """Read-only load chunks for a single document from data/chunks/<document_id>.jsonl.

    Validates extraction_class=W and content_class in {S1, S2}.
    Chunks are sorted stably by article_index then chunk_index.
    """
    file_path = chunks_dir / f"{document_id}.jsonl"
    if not file_path.exists():
        raise DocumentLoadError(f"chunk file not found: {file_path}")

    chunks: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DocumentLoadError(f"invalid JSON on line {line_number}: {exc}") from exc
            chunks.append(chunk)

    if not chunks:
        raise DocumentLoadError(f"chunk file is empty: {file_path}")

    _validate_chunks(chunks, document_id)

    chunks.sort(key=lambda c: (int(c.get("article_index", 0)), int(c.get("chunk_index", 0))))

    first = chunks[0]
    return LoadedDocument(
        document_id=document_id,
        title=str(first.get("title", "")),
        source_sha256=str(first.get("source_sha256", "")),
        extraction_class=str(first.get("extraction_class", "")),
        content_class=str(first.get("content_class", "")),
        chunks=chunks,
    )


def _validate_chunks(chunks: list[dict[str, Any]], document_id: str) -> None:
    extraction_classes: set[str] = set()
    content_classes: set[str] = set()
    source_sha256s: set[str] = set()

    for chunk in chunks:
        chunk_document_id = chunk.get("document_id")
        if chunk_document_id != document_id:
            raise DocumentLoadError(
                f"chunk document_id mismatch: expected {document_id}, got {chunk_document_id}"
            )

        extraction_class = chunk.get("extraction_class")
        if extraction_class:
            extraction_classes.add(str(extraction_class))

        content_class = chunk.get("content_class")
        if content_class:
            content_classes.add(str(content_class))

        source_sha256 = chunk.get("source_sha256")
        if source_sha256:
            source_sha256s.add(str(source_sha256))

    if extraction_classes != {"W"}:
        raise DocumentLoadError(
            f"extraction_class must be W for document {document_id}, got {extraction_classes}"
        )

    if not content_classes.issubset({"S1", "S2"}):
        raise DocumentLoadError(
            f"content_class must be S1 or S2 for document {document_id}, got {content_classes}"
        )

    if len(source_sha256s) != 1:
        raise DocumentLoadError(
            f"inconsistent source_sha256 for document {document_id}: {source_sha256s}"
        )
