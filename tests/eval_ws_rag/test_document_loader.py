from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.eval_ws_rag.document_loader import DocumentLoadError, load_document_chunks


def _write_chunks(tmp_path: Path, document_id: str, chunks: list[dict]) -> Path:
    file_path = tmp_path / f"{document_id}.jsonl"
    with file_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    return file_path


def _chunk(document_id: str, article_index: int, chunk_index: int, **overrides) -> dict:
    return {
        "chunk_id": f"{document_id}#article-{article_index}",
        "document_id": document_id,
        "title": "消防监督检查规定",
        "path": f"path > {article_index}",
        "text": "示例文本",
        "article_no": f"第{article_index}条",
        "article_index": article_index,
        "chunk_index": chunk_index,
        "source_sha256": "sha256_doc",
        "extraction_class": "W",
        "content_class": "S1",
        **overrides,
    }


def test_load_single_document():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks = [
            _chunk("doc_a", article_index=2, chunk_index=1),
            _chunk("doc_a", article_index=1, chunk_index=1),
        ]
        _write_chunks(tmp_path, "doc_a", chunks)

        result = load_document_chunks(tmp_path, "doc_a")
        assert len(result.chunks) == 2
        assert result.document_id == "doc_a"
        assert result.source_sha256 == "sha256_doc"
        assert result.content_class == "S1"
        assert result.extraction_class == "W"
        # 稳定排序：按 article_index，然后 chunk_index
        assert result.chunks[0]["article_index"] == 1
        assert result.chunks[1]["article_index"] == 2


def test_rejects_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_chunks(tmp_path, "doc_a", [])
        with pytest.raises(DocumentLoadError, match="empty"):
            load_document_chunks(tmp_path, "doc_a")


def test_rejects_broken_json():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        file_path = tmp_path / "doc_a.jsonl"
        file_path.write_text("not json\n", encoding="utf-8")
        with pytest.raises(DocumentLoadError):
            load_document_chunks(tmp_path, "doc_a")


def test_rejects_mixed_second_document():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks = [
            _chunk("doc_a", article_index=1, chunk_index=1),
            _chunk("doc_b", article_index=1, chunk_index=1),
        ]
        _write_chunks(tmp_path, "doc_a", chunks)
        with pytest.raises(DocumentLoadError, match="document_id"):
            load_document_chunks(tmp_path, "doc_a")


def test_rejects_non_w_extraction_class():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks = [_chunk("doc_a", article_index=1, chunk_index=1, extraction_class="PDF")]
        _write_chunks(tmp_path, "doc_a", chunks)
        with pytest.raises(DocumentLoadError, match="extraction_class"):
            load_document_chunks(tmp_path, "doc_a")


def test_rejects_unsupported_content_class():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks = [_chunk("doc_a", article_index=1, chunk_index=1, content_class="S3")]
        _write_chunks(tmp_path, "doc_a", chunks)
        with pytest.raises(DocumentLoadError, match="content_class"):
            load_document_chunks(tmp_path, "doc_a")


def test_rejects_inconsistent_source_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        chunks = [
            _chunk("doc_a", article_index=1, chunk_index=1, source_sha256="sha1"),
            _chunk("doc_a", article_index=2, chunk_index=1, source_sha256="sha2"),
        ]
        _write_chunks(tmp_path, "doc_a", chunks)
        with pytest.raises(DocumentLoadError, match="source_sha256"):
            load_document_chunks(tmp_path, "doc_a")


def test_real_ws_documents():
    chunks_dir = Path("data/chunks")
    if not chunks_dir.exists():
        pytest.skip("chunks 目录不存在")

    for document_id in ("doc_d97773f1500c", "doc_0e84d13a099b"):
        result = load_document_chunks(chunks_dir, document_id)
        assert result.document_id == document_id
        assert result.extraction_class == "W"
        assert result.content_class in ("S1", "S2")
        assert len(result.chunks) > 0
        # 顺序稳定
        for i in range(len(result.chunks) - 1):
            a = (result.chunks[i]["article_index"], result.chunks[i]["chunk_index"])
            b = (result.chunks[i + 1]["article_index"], result.chunks[i + 1]["chunk_index"])
            assert a <= b
