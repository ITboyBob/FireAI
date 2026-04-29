from pathlib import Path
import json
import runpy
import sys
from types import SimpleNamespace

import pytest

from app.services.embedder import SentenceTransformerEmbedder
from app.services.keyword_index import search_keyword_index
from app.services.vector_index import (
    append_vector_index,
    build_vector_index,
    VectorIndexConflictError,
)
from app.services.vector_store import FaissVectorStore, MissingVectorStoreDependencyError


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class FakeEmbedder:
    def encode(self, texts):
        vectors = []
        for text in texts:
            if "责任制" in text:
                vectors.append([3.0, 4.0])
                continue
            vectors.append([0.0, 5.0])
        return vectors


class RecordingVectorStore:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.vectors: list[list[float]] = []
        self.saved_path: Path | None = None

    def add(self, vectors):
        self.vectors = [list(vector) for vector in vectors]

    @property
    def vector_count(self):
        return len(self.vectors)

    def save(self, path: Path) -> Path:
        self.saved_path = path
        path.write_text("fake-index", encoding="utf-8")
        return path


class AppendableRecordingVectorStore(RecordingVectorStore):
    @classmethod
    def load(cls, path):
        store = cls(dimension=2)
        store.vectors = [[0.6, 0.8]]
        return store

    def add(self, vectors):
        self.vectors.extend([list(vector) for vector in vectors])


def test_build_vector_index_persists_mapping_and_store_artifacts(tmp_path: Path):
    chunks = [
        {"chunk_id": "a1", "text": "消防安全责任制", "path": "法 > 第二条"},
        {"chunk_id": "a2", "text": "损坏消防设施", "path": "法 > 第二十八条"},
    ]
    store = RecordingVectorStore(dimension=2)

    artifacts = build_vector_index(
        chunks,
        tmp_path,
        embedder=FakeEmbedder(),
        vector_store_factory=lambda dimension: store,
    )

    assert artifacts.index_path == tmp_path / "faiss.index"
    assert artifacts.vector_map_path == tmp_path / "vector_map.json"
    assert artifacts.chunk_count == 2
    assert artifacts.vector_dimension == 2
    assert store.saved_path == tmp_path / "faiss.index"
    assert store.vectors == [[0.6, 0.8], [0.0, 1.0]]

    payload = json.loads((tmp_path / "vector_map.json").read_text(encoding="utf-8"))
    assert payload == [
        {
            "position": 0,
            "chunk_id": "a1",
            "text": "消防安全责任制",
            "path": "法 > 第二条",
        },
        {
            "position": 1,
            "chunk_id": "a2",
            "text": "损坏消防设施",
            "path": "法 > 第二十八条",
        },
    ]


def test_append_vector_index_extends_positions_and_rejects_duplicate_document(tmp_path):
    build_vector_index(
        [{"chunk_id": "old-1", "document_id": "old_doc", "text": "消防安全责任制"}],
        tmp_path,
        embedder=FakeEmbedder(),
        vector_store_factory=lambda dimension: RecordingVectorStore(dimension),
    )

    artifacts = append_vector_index(
        [{"chunk_id": "new-1", "document_id": "new_doc", "text": "损坏消防设施"}],
        tmp_path,
        embedder=FakeEmbedder(),
        document_id="new_doc",
        vector_store_loader=AppendableRecordingVectorStore.load,
    )

    vector_map = json.loads(artifacts.vector_map_path.read_text(encoding="utf-8"))
    assert [item["position"] for item in vector_map] == [0, 1]
    assert [item["document_id"] for item in vector_map] == ["old_doc", "new_doc"]
    assert artifacts.vector_count == 2
    assert artifacts.vector_store.vectors[0] == [0.6, 0.8]
    assert len(artifacts.vector_store.vectors) == 2

    with pytest.raises(VectorIndexConflictError, match="向量映射已有该 document_id"):
        append_vector_index(
            [{"chunk_id": "new-2", "document_id": "new_doc", "text": "重复"}],
            tmp_path,
            embedder=FakeEmbedder(),
            document_id="new_doc",
            vector_store_loader=AppendableRecordingVectorStore.load,
        )


def test_append_vector_index_encodes_before_loading_vector_store(tmp_path):
    events: list[str] = []

    class OrderedFakeEmbedder(FakeEmbedder):
        def encode(self, texts):
            events.append("encode")
            return super().encode(texts)

    def load_store(path):
        events.append("load-store")
        return AppendableRecordingVectorStore.load(path)

    build_vector_index(
        [{"chunk_id": "old-1", "document_id": "old_doc", "text": "消防安全责任制"}],
        tmp_path,
        embedder=FakeEmbedder(),
        vector_store_factory=lambda dimension: RecordingVectorStore(dimension),
    )

    append_vector_index(
        [{"chunk_id": "new-1", "document_id": "new_doc", "text": "损坏消防设施"}],
        tmp_path,
        embedder=OrderedFakeEmbedder(),
        document_id="new_doc",
        vector_store_loader=load_store,
    )

    assert events[:2] == ["encode", "load-store"]


def test_sentence_transformer_embedder_uses_document_and_query_encoders(monkeypatch):
    calls: list[tuple[str, list[str], dict]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name_or_path: str, *, device: str | None = None):
            self.model_name_or_path = model_name_or_path
            self.device = device
            self.max_seq_length = None
            self.prompts = {"query": "query: ", "document": "document: "}

        def encode_document(self, texts, **kwargs):
            calls.append(("document", list(texts), kwargs))
            return [[1.0, 0.0]]

        def encode_query(self, texts, **kwargs):
            calls.append(("query", list(texts), kwargs))
            return [[0.0, 1.0]]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    embedder = SentenceTransformerEmbedder(
        model_name_or_path="local-model",
        device="cpu",
        batch_size=8,
        max_seq_length=256,
    )

    assert embedder.encode_documents(["消防安全责任制"]) == [[1.0, 0.0]]
    assert embedder.encode_queries(["消防设施"]) == [[0.0, 1.0]]
    assert embedder.encode(["损坏消防设施"]) == [[1.0, 0.0]]

    assert calls == [
        (
            "document",
            ["消防安全责任制"],
            {
                "batch_size": 8,
                "show_progress_bar": False,
                "convert_to_numpy": True,
                "normalize_embeddings": True,
            },
        ),
        (
            "query",
            ["消防设施"],
            {
                "batch_size": 8,
                "show_progress_bar": False,
                "convert_to_numpy": True,
                "normalize_embeddings": True,
            },
        ),
        (
            "document",
            ["损坏消防设施"],
            {
                "batch_size": 8,
                "show_progress_bar": False,
                "convert_to_numpy": True,
                "normalize_embeddings": True,
            },
        ),
    ]
    assert embedder._model is not None
    assert embedder._model.max_seq_length == 256


def test_sentence_transformer_embedder_falls_back_to_encode_for_promptless_query_models(monkeypatch):
    calls: list[tuple[str, list[str], dict]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name_or_path: str, *, device: str | None = None):
            self.model_name_or_path = model_name_or_path
            self.device = device
            self.max_seq_length = None
            self.prompts = {"query": "", "document": ""}

        def encode(self, texts, **kwargs):
            calls.append(("encode", list(texts), kwargs))
            return [[0.0, 1.0]]

        def encode_query(self, texts, **kwargs):
            calls.append(("query", list(texts), kwargs))
            return [[1.0, 0.0]]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    embedder = SentenceTransformerEmbedder(model_name_or_path="local-model", device="cpu")

    assert embedder.encode_queries(["消防法第二条"]) == [[0.0, 1.0]]
    assert calls == [
        (
            "encode",
            ["消防法第二条"],
            {
                "batch_size": 32,
                "show_progress_bar": False,
                "convert_to_numpy": True,
                "normalize_embeddings": True,
            },
        )
    ]


def test_faiss_vector_store_raises_clear_error_when_dependencies_missing(monkeypatch):
    from app.services import vector_store as vector_store_module

    def _raise_missing_dependency():
        raise MissingVectorStoreDependencyError("缺少 `numpy` 和 `faiss-cpu` 依赖。")

    monkeypatch.setattr(
        vector_store_module,
        "_load_faiss_dependencies",
        _raise_missing_dependency,
    )

    store = FaissVectorStore(dimension=2)

    with pytest.raises(MissingVectorStoreDependencyError, match="faiss-cpu"):
        store.add([[1.0, 0.0]])


def test_build_indexes_builds_keyword_and_vector_outputs_from_chunk_jsonl(
    tmp_path: Path,
):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (chunks_dir / "sample.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "chunk_id": "a1",
                        "document_id": "doc-1",
                        "title": "消防法",
                        "path": "法 > 第二条",
                        "text": "国家实行消防安全责任制。",
                        "article_no": "第二条",
                        "chapter_title": "第一章 总则",
                        "region": "全国",
                        "promulgated_on": None,
                        "effective_on": "2009年5月1日",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "chunk_id": "a2",
                        "document_id": "doc-1",
                        "title": "消防法",
                        "path": "法 > 第二十八条",
                        "text": "任何单位不得损坏消防设施。",
                        "article_no": "第二十八条",
                        "chapter_title": "第三章",
                        "region": "全国",
                        "promulgated_on": None,
                        "effective_on": "2009年5月1日",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    store = RecordingVectorStore(dimension=2)
    module_globals = runpy.run_path(str(PROJECT_ROOT / "scripts" / "build_index.py"))
    build_indexes = module_globals["build_indexes"]

    summary = build_indexes(
        chunks_dir,
        tmp_path / "index",
        embedder=FakeEmbedder(),
        vector_store_factory=lambda dimension: store,
    )

    assert summary["chunk_count"] == 2
    assert summary["keyword_db"] == tmp_path / "index" / "retrieval.db"
    assert summary["vector_index"] == tmp_path / "index" / "faiss.index"
    assert summary["vector_map"] == tmp_path / "index" / "vector_map.json"
    assert search_keyword_index("消防设施", summary["keyword_db"], top_k=3)[0]["chunk_id"] == "a2"
    assert json.loads(summary["vector_map"].read_text(encoding="utf-8"))[1]["chunk_id"] == "a2"
