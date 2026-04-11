from pathlib import Path
import os

from app.services.knowledge_version import KnowledgeVersionResolver


def test_resolve_knowledge_version_is_stable_and_changes_with_artifacts(tmp_path: Path):
    (tmp_path / "retrieval.db").write_text("keyword", encoding="utf-8")
    (tmp_path / "faiss.index").write_bytes(b"vector-index")
    (tmp_path / "vector_map.json").write_text('{"0": "chunk-1"}', encoding="utf-8")

    resolver = KnowledgeVersionResolver(index_dir=tmp_path)

    before = resolver.resolve()
    again = resolver.resolve()

    assert before == again
    assert before.startswith("kb:")

    os.utime(tmp_path / "vector_map.json", None)
    (tmp_path / "vector_map.json").write_text('{"0": "chunk-2"}', encoding="utf-8")

    after = resolver.resolve()

    assert after != before
