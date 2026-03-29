import sys
from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import Settings
from app.services.embedder import SentenceTransformerEmbedder
from app.services.keyword_index import build_keyword_index
from app.services.vector_index import build_vector_index


def load_chunks(chunks_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(chunks_dir.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            payload = line.strip()
            if not payload:
                continue
            try:
                chunks.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} 不是合法 JSONL") from exc

    return chunks


def build_indexes(
    chunks_dir: Path,
    output_dir: Path,
    *,
    embedder,
    vector_store_factory=None,
) -> dict[str, Path | int]:
    chunks = load_chunks(chunks_dir)
    if not chunks:
        raise ValueError(f"{chunks_dir} 下没有可建索引的 chunk")

    output_dir.mkdir(parents=True, exist_ok=True)
    keyword_db_path = build_keyword_index(chunks, output_dir / "retrieval.db")
    vector_artifacts = build_vector_index(
        chunks,
        output_dir,
        embedder=embedder,
        vector_store_factory=vector_store_factory,
    )
    return {
        "keyword_db": keyword_db_path,
        "vector_index": vector_artifacts.index_path,
        "vector_map": vector_artifacts.vector_map_path,
        "chunk_count": vector_artifacts.chunk_count,
    }


def main() -> int:
    settings = Settings()
    if not settings.embedding_model_name:
        raise ValueError(
            "未配置 EMBEDDING_MODEL_NAME，无法构建真实向量索引。"
        )

    embedder = SentenceTransformerEmbedder(
        model_name_or_path=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_seq_length=settings.embedding_max_seq_length,
    )
    summary = build_indexes(
        settings.data_dir / "chunks",
        settings.index_dir,
        embedder=embedder,
    )
    print(f"chunks={summary['chunk_count']}")
    print(f"keyword_db={summary['keyword_db']}")
    print(f"vector_index={summary['vector_index']}")
    print(f"vector_map={summary['vector_map']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
