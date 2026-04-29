from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from app.services.embedder import normalize_vectors
from app.services.vector_store import FAISS_INDEX_FILENAME, FaissVectorStore, VectorStore


VECTOR_MAP_FILENAME = "vector_map.json"


@dataclass(frozen=True)
class VectorIndexArtifacts:
    index_path: Path
    vector_map_path: Path
    chunk_count: int
    vector_dimension: int
    vector_count: int
    vector_store: VectorStore


class VectorIndexConflictError(RuntimeError):
    pass


def build_vector_index(
    chunks: list[dict[str, Any]],
    output_dir: Path,
    *,
    embedder: Any,
    vector_store_factory: Callable[[int], VectorStore] | None = None,
) -> VectorIndexArtifacts:
    if not chunks:
        raise ValueError("chunks must not be empty")

    texts = [str(chunk.get("text", "")).strip() for chunk in chunks]
    if any(not text for text in texts):
        raise ValueError("each chunk must include non-empty text")

    raw_vectors = _encode_documents(embedder, texts)
    if len(raw_vectors) != len(chunks):
        raise ValueError("embedder output count does not match chunk count")

    vectors = normalize_vectors(raw_vectors)
    vector_dimension = _validate_vector_dimensions(vectors)

    output_dir.mkdir(parents=True, exist_ok=True)
    store = (
        vector_store_factory(vector_dimension)
        if vector_store_factory is not None
        else FaissVectorStore(vector_dimension)
    )
    store.add(vectors)

    index_path = store.save(output_dir / FAISS_INDEX_FILENAME)
    vector_map_path = output_dir / VECTOR_MAP_FILENAME
    vector_map_path.write_text(
        json.dumps(_build_vector_map(chunks), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return VectorIndexArtifacts(
        index_path=index_path,
        vector_map_path=vector_map_path,
        chunk_count=len(chunks),
        vector_dimension=vector_dimension,
        vector_count=store.vector_count,
        vector_store=store,
    )


def append_vector_index(
    chunks: list[dict[str, Any]],
    output_dir: Path,
    *,
    embedder: Any,
    document_id: str,
    vector_store_loader: Callable[[Path], VectorStore] = FaissVectorStore.load,
) -> VectorIndexArtifacts:
    index_path = output_dir / FAISS_INDEX_FILENAME
    vector_map_path = output_dir / VECTOR_MAP_FILENAME
    if not index_path.exists():
        raise FileNotFoundError(f"向量索引不存在: {index_path}")
    if not vector_map_path.exists():
        raise FileNotFoundError(f"向量映射不存在: {vector_map_path}")

    existing_vector_map = load_vector_map(vector_map_path)
    validate_vector_map(existing_vector_map)
    if any(item["document_id"] == document_id for item in existing_vector_map):
        raise VectorIndexConflictError(f"向量映射已有该 document_id: {document_id}")
    if not chunks:
        raise ValueError("chunks must not be empty")
    if any(chunk.get("document_id") != document_id for chunk in chunks):
        raise ValueError(f"chunks document_id 必须全部等于: {document_id}")

    texts = [str(chunk.get("text", "")).strip() for chunk in chunks]
    if any(not text for text in texts):
        raise ValueError("each chunk must include non-empty text")

    store = vector_store_loader(index_path)
    if store.vector_count != len(existing_vector_map):
        raise ValueError("faiss.index 与 vector_map.json 数量不一致")

    raw_vectors = _encode_documents(embedder, texts)
    if len(raw_vectors) != len(chunks):
        raise ValueError("embedder output count does not match chunk count")
    vectors = normalize_vectors(raw_vectors)
    vector_dimension = _validate_vector_dimensions(vectors)
    if store.dimension != vector_dimension:
        raise ValueError("vector dimensions do not match the configured store dimension")

    store.add(vectors)
    appended_vector_map = [
        *existing_vector_map,
        *_build_vector_map(chunks, start_position=len(existing_vector_map)),
    ]
    validate_vector_map(appended_vector_map)
    if store.vector_count != len(appended_vector_map):
        raise ValueError("faiss.index 与 vector_map.json 数量不一致")

    saved_index_path = store.save(index_path)
    vector_map_path.write_text(
        json.dumps(appended_vector_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return VectorIndexArtifacts(
        index_path=saved_index_path,
        vector_map_path=vector_map_path,
        chunk_count=len(chunks),
        vector_dimension=vector_dimension,
        vector_count=store.vector_count,
        vector_store=store,
    )


def load_vector_map(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_vector_map(vector_map: list[dict[str, Any]]) -> None:
    if not isinstance(vector_map, list):
        raise ValueError("vector_map must be a list")

    seen_chunk_ids: set[str] = set()
    for expected_position, item in enumerate(vector_map):
        if not isinstance(item, dict):
            raise ValueError("vector_map items must be objects")
        if item.get("position") != expected_position:
            raise ValueError("vector_map positions must be contiguous from 0")
        chunk_id = item.get("chunk_id")
        document_id = item.get("document_id")
        if not chunk_id or not document_id:
            raise ValueError("vector_map items must include chunk_id and document_id")
        if str(chunk_id) in seen_chunk_ids:
            raise ValueError(f"vector_map chunk_id duplicated: {chunk_id}")
        seen_chunk_ids.add(str(chunk_id))


def _encode_documents(embedder: Any, texts: Sequence[str]) -> list[list[float]]:
    if hasattr(embedder, "encode_documents"):
        vectors = embedder.encode_documents(texts)
    elif hasattr(embedder, "encode"):
        vectors = embedder.encode(texts)
    else:
        raise TypeError("embedder must define encode_documents() or encode()")

    if not isinstance(vectors, Sequence):
        raise TypeError("embedder output must be a sequence of vectors")

    return [
        [float(value) for value in vector]
        for vector in vectors
    ]


def _validate_vector_dimensions(vectors: Sequence[Sequence[float]]) -> int:
    if not vectors:
        raise ValueError("vectors must not be empty")

    dimension = len(vectors[0])
    if dimension <= 0:
        raise ValueError("embedding dimension must be positive")

    for vector in vectors:
        if len(vector) != dimension:
            raise ValueError("embedding vectors must all share the same dimension")

    return dimension


def _build_vector_map(
    chunks: Sequence[dict[str, Any]],
    *,
    start_position: int = 0,
) -> list[dict[str, Any]]:
    return [
        {"position": start_position + offset, **chunk}
        for offset, chunk in enumerate(chunks)
    ]
