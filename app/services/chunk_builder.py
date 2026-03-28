from pathlib import Path
from typing import Any
import json


DEFAULT_MAX_CHUNK_CHARS = 300


def build_chunks(
    structured: dict[str, Any],
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive")

    chunks: list[dict[str, Any]] = []
    articles = structured.get("articles", [])

    for article_index, article in enumerate(articles, start=1):
        heading_path = _normalize_heading_path(article.get("heading_path"))
        path = _build_chunk_path(
            structured["title"],
            heading_path,
            article["article_no"],
        )
        chunk_texts = _split_article_text(article["text"], max_chunk_chars)
        chunk_total = len(chunk_texts)

        for chunk_index, chunk_text in enumerate(chunk_texts, start=1):
            chunk_id = f'{structured["document_id"]}#article-{article_index}'
            if chunk_total > 1:
                chunk_id = f"{chunk_id}-part-{chunk_index}"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": structured["document_id"],
                    "title": structured["title"],
                    "path": path,
                    "text": chunk_text,
                    "article_no": article["article_no"],
                    "article_index": article_index,
                    "chapter_title": article.get("chapter_title"),
                    "heading_path": heading_path,
                    "issuing_authority": structured.get("issuing_authority"),
                    "region": structured.get("region"),
                    "promulgated_on": structured.get("promulgated_on"),
                    "effective_on": structured.get("effective_on"),
                    "chunk_index": chunk_index,
                    "chunk_total": chunk_total,
                }
            )

    return chunks


def write_chunks(
    chunks: list[dict[str, Any]],
    document_id: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{document_id}.jsonl"
    output_path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks),
        encoding="utf-8",
    )
    return output_path


def _normalize_heading_path(raw_heading_path: Any) -> list[str]:
    if not raw_heading_path:
        return []
    return [str(item) for item in raw_heading_path if str(item).strip()]


def _build_chunk_path(title: str, heading_path: list[str], article_no: str) -> str:
    path_parts = [title, *heading_path, article_no]
    return " > ".join(path_parts)


def _split_article_text(article_text: str, max_chunk_chars: int) -> list[str]:
    text = article_text.strip()
    if not text:
        return []

    paragraphs = [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]
    if len(paragraphs) <= 1 or len(text) <= max_chunk_chars:
        return [text]

    chunk_texts: list[str] = []
    current_parts: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        separator_length = 1 if current_parts else 0
        if current_parts and current_length + separator_length + paragraph_length > max_chunk_chars:
            chunk_texts.append("\n".join(current_parts))
            current_parts = [paragraph]
            current_length = paragraph_length
            continue

        current_parts.append(paragraph)
        current_length += separator_length + paragraph_length

    if current_parts:
        chunk_texts.append("\n".join(current_parts))

    return chunk_texts
