from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


FAISS_INDEX_FILENAME = "faiss.index"


class MissingVectorStoreDependencyError(RuntimeError):
    """Raised when optional vector-store dependencies are unavailable."""


class VectorStore(Protocol):
    dimension: int

    @property
    def vector_count(self) -> int:
        """Return the number of vectors currently stored."""

    def add(self, vectors: Sequence[Sequence[float]]) -> None:
        """Add vectors to the store."""

    def save(self, path: Path) -> Path:
        """Persist the store to disk."""

    def search(self, query_vector: Sequence[float], *, top_k: int) -> list[dict[str, float | int]]:
        """Search the store and return vector positions with scores."""


@dataclass
class FaissVectorStore:
    dimension: int
    _index: Any | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ValueError("dimension must be positive")

    @property
    def vector_count(self) -> int:
        return int(self._get_or_create_index().ntotal)

    def add(self, vectors: Sequence[Sequence[float]]) -> None:
        if not vectors:
            return

        numpy, _ = _load_faiss_dependencies()
        index = self._get_or_create_index()
        matrix = numpy.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != self.dimension:
            raise ValueError("vector dimensions do not match the configured store dimension")
        index.add(matrix)

    def save(self, path: Path) -> Path:
        _, faiss = _load_faiss_dependencies()
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._get_or_create_index(), str(path))
        return path

    def search(self, query_vector: Sequence[float], *, top_k: int) -> list[dict[str, float | int]]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        numpy, _ = _load_faiss_dependencies()
        matrix = numpy.asarray([query_vector], dtype="float32")
        if matrix.shape[1] != self.dimension:
            raise ValueError("query vector dimensions do not match the configured store dimension")

        scores, positions = self._get_or_create_index().search(matrix, top_k)
        results: list[dict[str, float | int]] = []
        for position, score in zip(positions[0], scores[0], strict=True):
            if int(position) < 0:
                continue
            results.append({"position": int(position), "score": float(score)})
        return results

    @classmethod
    def load(cls, path: Path) -> "FaissVectorStore":
        _, faiss = _load_faiss_dependencies()
        index = faiss.read_index(str(path))
        store = cls(dimension=index.d)
        store._index = index
        return store

    def _get_or_create_index(self) -> Any:
        _, faiss = _load_faiss_dependencies()
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dimension)
        return self._index


def _load_faiss_dependencies() -> tuple[Any, Any]:
    try:
        import numpy
    except ImportError as exc:
        raise MissingVectorStoreDependencyError(
            "缺少 `numpy` 依赖。请先在 `fire` 环境安装 `numpy` 和 `faiss-cpu`。"
        ) from exc

    try:
        import faiss
    except ImportError as exc:
        raise MissingVectorStoreDependencyError(
            "缺少 `faiss-cpu` 依赖。请先在 `fire` 环境安装 `numpy` 和 `faiss-cpu`。"
        ) from exc

    return numpy, faiss
