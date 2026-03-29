from collections.abc import Sequence
from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Protocol


class MissingEmbeddingDependencyError(RuntimeError):
    """Raised when optional local embedding dependencies are unavailable."""


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode texts for document indexing."""


def normalize_vector(vector: Sequence[float]) -> list[float]:
    length = sqrt(sum(float(value) * float(value) for value in vector))
    if length == 0:
        raise ValueError("embedding vector must not be zero-length")
    return [float(value) / length for value in vector]


def normalize_vectors(vectors: Sequence[Sequence[float]]) -> list[list[float]]:
    return [normalize_vector(vector) for vector in vectors]


def coerce_vector_rows(vectors: Any) -> list[list[float]]:
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()

    if not isinstance(vectors, Sequence):
        raise TypeError("embedding output must be a sequence of vectors")

    rows: list[list[float]] = []
    for vector in vectors:
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        if not isinstance(vector, Sequence):
            raise TypeError("each embedding vector must be a sequence")
        rows.append([float(value) for value in vector])

    return rows


@dataclass
class SentenceTransformerEmbedder:
    model_name_or_path: str
    device: str | None = None
    batch_size: int = 32
    max_seq_length: int | None = None
    _model: Any | None = field(default=None, init=False, repr=False)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return self.encode_documents(texts)

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts, method_name="encode_document")

    def encode_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts, method_name="encode_query")

    def _encode(self, texts: Sequence[str], *, method_name: str) -> list[list[float]]:
        items = [text for text in texts if text and text.strip()]
        if not items:
            return []

        model = self._get_model()
        encoder = getattr(model, method_name, None) or getattr(model, "encode")
        vectors = encoder(
            items,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return coerce_vector_rows(vectors)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MissingEmbeddingDependencyError(
                "缺少 `sentence-transformers` 依赖。请先在 `fire` 环境安装它，再运行真实本地嵌入。"
            ) from exc

        model = SentenceTransformer(self.model_name_or_path, device=self.device)
        if self.max_seq_length is not None and hasattr(model, "max_seq_length"):
            model.max_seq_length = self.max_seq_length

        self._model = model
        return model
