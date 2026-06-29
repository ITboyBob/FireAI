from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

from app.services.legal_intermediate import (
    LegalDocumentIntermediate,
    validate_legal_intermediate,
)
from app.services.structure_parser import ParsedDocument


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


def build_intermediate_chunks(
    intermediate: LegalDocumentIntermediate,
    parsed: ParsedDocument,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    validate_legal_intermediate(intermediate)
    if intermediate.boundary.status != "confirmed":
        raise ValueError("只有 confirmed 中间格式可以进入切块")
    if parsed.document_id != intermediate.document_id:
        raise ValueError("结构化文档的 document_id 与中间格式不一致")
    if parsed.title != intermediate.target.title:
        raise ValueError("结构化文档标题与 confirmed 目标正文不一致")
    if parsed.source_sha256 != intermediate.source_ref.source_sha256:
        raise ValueError("结构化文档的来源摘要与中间格式不一致")
    if parsed.extraction_class != intermediate.extraction_class.value:
        raise ValueError("结构化文档的提取分类与中间格式不一致")
    if parsed.content_class != intermediate.content_class.value:
        raise ValueError("结构化文档的内容分类与中间格式不一致")
    if parsed.boundary_status != "confirmed":
        raise ValueError("结构化文档未绑定 confirmed 边界状态")
    if parsed.version_basis != intermediate.target.version_basis:
        raise ValueError("结构化文档的版本依据与中间格式不一致")
    if not parsed.articles or any(
        article.source_span is None for article in parsed.articles
    ):
        raise ValueError("结构化文档的条文来源范围不完整")

    chunks = build_chunks(asdict(parsed), max_chunk_chars=max_chunk_chars)
    covered_article_indexes = {
        int(chunk["article_index"]) for chunk in chunks
    }
    expected_article_indexes = set(range(1, len(parsed.articles) + 1))
    if covered_article_indexes != expected_article_indexes:
        raise ValueError("切块结果未完整覆盖 confirmed 条文")

    enriched_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        article_index = int(chunk["article_index"])
        article = parsed.articles[article_index - 1]
        if article.source_span is None:
            raise ValueError("切块结果对应条文缺少来源范围")
        enriched_chunks.append(
            {
                **chunk,
                "source_sha256": intermediate.source_ref.source_sha256,
                "source_span": asdict(article.source_span),
                "extraction_class": intermediate.extraction_class.value,
                "content_class": intermediate.content_class.value,
                "boundary_status": intermediate.boundary.status,
            }
        )
    return enriched_chunks


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
