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
    )


def load_vector_map(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _build_vector_map(chunks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"position": position, **chunk}
        for position, chunk in enumerate(chunks)
    ]
