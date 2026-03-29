from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.embedder import normalize_vector
from app.services.keyword_index import search_keyword_index
from app.services.query_normalizer import NormalizedQuery, normalize_query
from app.services.vector_index import load_vector_map
from app.services.vector_store import FaissVectorStore


KeywordSearchFn = Callable[..., list[dict[str, Any]]]


@dataclass
class Retriever:
    keyword_db_path: Path
    vector_store: Any | None = None
    vector_map: Sequence[dict[str, Any]] = field(default_factory=list)
    embedder: Any | None = None
    keyword_search: KeywordSearchFn = search_keyword_index
    candidate_multiplier: int = 3
    keyword_weight: float = 0.6
    vector_weight: float = 0.4

    @classmethod
    def from_disk(
        cls,
        *,
        keyword_db_path: Path,
        vector_index_path: Path,
        vector_map_path: Path,
        embedder: Any | None = None,
        keyword_search: KeywordSearchFn = search_keyword_index,
    ) -> "Retriever":
        return cls(
            keyword_db_path=keyword_db_path,
            vector_store=FaissVectorStore.load(vector_index_path),
            vector_map=load_vector_map(vector_map_path),
            embedder=embedder,
            keyword_search=keyword_search,
        )

    def search(self, query: str | NormalizedQuery, *, top_k: int = 5) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        normalized = query if isinstance(query, NormalizedQuery) else normalize_query(query)
        candidate_limit = max(top_k * self.candidate_multiplier, top_k)
        keyword_hits = self._search_keywords(normalized, top_k=candidate_limit)
        vector_hits = self._search_vectors(normalized, top_k=candidate_limit)
        return fuse_results(
            keyword_hits,
            vector_hits,
            top_k=top_k,
            keyword_weight=self.keyword_weight,
            vector_weight=self.vector_weight,
        )

    def _search_keywords(self, normalized: NormalizedQuery, *, top_k: int) -> list[dict[str, Any]]:
        hits_by_id: dict[str, dict[str, Any]] = {}
        terms = normalized.keyword_terms or [normalized.cleaned]
        for term in terms:
            if not term:
                continue
            rows = self.keyword_search(
                term,
                self.keyword_db_path,
                top_k=top_k,
                region=normalized.region,
                promulgated_on=normalized.promulgated_on,
                effective_on=normalized.effective_on,
            )
            for row in rows:
                if not _matches_metadata(row, normalized):
                    continue
                chunk_id = str(row["chunk_id"])
                candidate = {**row, "source": "keyword"}
                existing = hits_by_id.get(chunk_id)
                if existing is None or _keyword_score_value(candidate.get("score", 0.0)) > _keyword_score_value(
                    existing.get("score", 0.0)
                ):
                    hits_by_id[chunk_id] = candidate
        return list(hits_by_id.values())

    def _search_vectors(self, normalized: NormalizedQuery, *, top_k: int) -> list[dict[str, Any]]:
        if self.embedder is None or self.vector_store is None or not self.vector_map:
            return []

        query_text = normalized.vector_query or normalized.cleaned
        vectors = _encode_queries(self.embedder, [query_text])
        if not vectors:
            return []

        vector_positions = self.vector_store.search(vectors[0], top_k=top_k)
        chunks_by_position = {
            int(chunk["position"]): chunk
            for chunk in self.vector_map
            if "position" in chunk
        }
        hits: list[dict[str, Any]] = []
        for row in vector_positions:
            chunk = chunks_by_position.get(int(row["position"]))
            if chunk is None:
                continue
            candidate = {
                **chunk,
                "score": float(row["score"]),
                "source": "vector",
            }
            if _matches_metadata(candidate, normalized):
                hits.append(candidate)
        return hits


def fuse_results(
    keyword_hits: Sequence[dict[str, Any]],
    vector_hits: Sequence[dict[str, Any]],
    *,
    top_k: int,
    keyword_weight: float = 0.6,
    vector_weight: float = 0.4,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    merged: dict[str, dict[str, Any]] = {}
    keyword_scores = _normalize_scores(keyword_hits, source="keyword")
    vector_scores = _normalize_scores(vector_hits, source="vector")

    for hit, score in zip(keyword_hits, keyword_scores, strict=True):
        _merge_hit(merged, hit, source="keyword", normalized_score=score)
    for hit, score in zip(vector_hits, vector_scores, strict=True):
        _merge_hit(merged, hit, source="vector", normalized_score=score)

    results: list[dict[str, Any]] = []
    for item in merged.values():
        combined_score = item["keyword_score"] * keyword_weight + item["vector_score"] * vector_weight
        results.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"keyword_score", "vector_score", "_sources"}
            }
            | {
                "score": combined_score,
                "keyword_score": item["keyword_score"],
                "vector_score": item["vector_score"],
                "sources": sorted(item["_sources"]),
            }
        )

    results.sort(
        key=lambda item: (
            -float(item["score"]),
            -float(item["keyword_score"]),
            -float(item["vector_score"]),
            str(item["chunk_id"]),
        )
    )
    return results[:top_k]


def _encode_queries(embedder: Any, texts: Sequence[str]) -> list[list[float]]:
    if hasattr(embedder, "encode_queries"):
        vectors = embedder.encode_queries(texts)
    elif hasattr(embedder, "encode_query"):
        vectors = embedder.encode_query(texts)
    elif hasattr(embedder, "encode"):
        vectors = embedder.encode(texts)
    else:
        raise TypeError("embedder must define encode_queries(), encode_query(), or encode()")

    rows: list[list[float]] = []
    for vector in vectors:
        rows.append(normalize_vector([float(value) for value in vector]))
    return rows


def _matches_metadata(candidate: dict[str, Any], normalized: NormalizedQuery) -> bool:
    if len(normalized.canonical_terms) == 1 and candidate.get("title") != normalized.canonical_terms[0]:
        return False
    if normalized.region and candidate.get("region") != normalized.region:
        return False
    if normalized.article_no and candidate.get("article_no") != normalized.article_no:
        return False
    if normalized.promulgated_on and candidate.get("promulgated_on") != normalized.promulgated_on:
        return False
    if normalized.effective_on and candidate.get("effective_on") != normalized.effective_on:
        return False
    return True


def _normalize_scores(hits: Sequence[dict[str, Any]], *, source: str) -> list[float]:
    if not hits:
        return []

    raw_scores = [float(hit.get("score", 0.0)) for hit in hits]
    if source == "keyword" and any(score < 0 for score in raw_scores):
        adjusted_scores = [max(0.0, -score) for score in raw_scores]
    else:
        adjusted_scores = [max(0.0, score) for score in raw_scores]

    maximum = max(adjusted_scores)
    minimum = min(adjusted_scores)
    if maximum == minimum:
        value = 1.0 if maximum > 0 else 0.0
        return [value for _ in adjusted_scores]
    return [(score - minimum) / (maximum - minimum) for score in adjusted_scores]


def _merge_hit(
    merged: dict[str, dict[str, Any]],
    hit: dict[str, Any],
    *,
    source: str,
    normalized_score: float,
) -> None:
    chunk_id = str(hit["chunk_id"])
    existing = merged.get(chunk_id)
    base = {key: value for key, value in hit.items() if key not in {"source"}}
    if existing is None:
        merged[chunk_id] = {
            **base,
            "keyword_score": 0.0,
            "vector_score": 0.0,
            "_sources": set(),
        }
        existing = merged[chunk_id]
    else:
        for key, value in base.items():
            existing.setdefault(key, value)

    if source == "keyword":
        existing["keyword_score"] = max(existing["keyword_score"], normalized_score)
    else:
        existing["vector_score"] = max(existing["vector_score"], normalized_score)
    existing["_sources"].add(source)


def _keyword_score_value(score: Any) -> float:
    numeric = float(score)
    return max(0.0, -numeric) if numeric < 0 else max(0.0, numeric)
