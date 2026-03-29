from pathlib import Path

from app.api import chat as chat_api


def test_build_retriever_primes_embedder_before_loading_vector_store(monkeypatch):
    events: list[object] = []

    class FakeEmbedder:
        def __init__(self, *, model_name_or_path, device, batch_size, max_seq_length):
            events.append(
                (
                    "init",
                    model_name_or_path,
                    device,
                    batch_size,
                    max_seq_length,
                )
            )

        def encode_queries(self, texts):
            events.append(("warmup", list(texts)))
            return [[1.0, 0.0]]

    def fake_retriever_factory(**kwargs):
        events.append(("factory", kwargs["keyword_db_path"], kwargs["vector_index_path"], kwargs["vector_map_path"]))
        return {"embedder": kwargs["embedder"]}

    monkeypatch.setattr(chat_api, "SentenceTransformerEmbedder", FakeEmbedder)
    chat_api._build_retriever.cache_clear()

    retriever = chat_api._build_retriever(
        keyword_db_path=Path("data/index/retrieval.db"),
        vector_index_path=Path("data/index/faiss.index"),
        vector_map_path=Path("data/index/vector_map.json"),
        embedding_model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        embedding_device="cpu",
        embedding_batch_size=32,
        embedding_max_seq_length=None,
        retriever_factory=fake_retriever_factory,
    )

    assert retriever["embedder"] is not None
    assert events == [
        (
            "init",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "cpu",
            32,
            None,
        ),
        ("warmup", ["warmup"]),
        (
            "factory",
            Path("data/index/retrieval.db"),
            Path("data/index/faiss.index"),
            Path("data/index/vector_map.json"),
        ),
    ]
