from pathlib import Path
import json
import runpy
import subprocess

from app.services.normalizer import TEXTUTIL_BINARY

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MINI_FIRE_LAW = """中华人民共和国消防法
第一章 总则
第一条 为了预防火灾，保护人身和财产安全，制定本法。
第二条 国家实行消防安全责任制。
"""

MINI_HEBEI_REGULATION = """河北省消防条例
第一章 总则
第一条 为了加强消防工作，预防火灾，制定本条例。
第二条 本条例适用于河北省行政区域内的消防安全活动。
"""


class FakeEmbedder:
    def encode_documents(self, texts):
        vectors: list[list[float]] = []
        for index, text in enumerate(texts):
            length_signal = float(max(len(text.strip()), 1))
            vectors.append([length_signal, float(index + 1)])
        return vectors


class RecordingVectorStore:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.vectors: list[list[float]] = []

    def add(self, vectors):
        self.vectors = [list(vector) for vector in vectors]

    def save(self, path: Path) -> Path:
        path.write_text("fake-index", encoding="utf-8")
        return path


def _write_docx(source_text: str, output_path: Path) -> None:
    plain_text_path = output_path.with_suffix(".txt")
    plain_text_path.write_text(source_text, encoding="utf-8")
    subprocess.run(
        [
            TEXTUTIL_BINARY,
            "-convert",
            "docx",
            str(plain_text_path),
            "-output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_pipeline_creates_expected_outputs(tmp_path, monkeypatch):
    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)

    _write_docx(MINI_FIRE_LAW, raw_dir / "消防法--2019年4月23日.docx")
    _write_docx(MINI_HEBEI_REGULATION, raw_dir / "河北省消防条例.docx")

    monkeypatch.setenv("RAW_CORPUS_DIR", str(raw_dir))
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    corpus_module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "build_corpus.py"))
    index_module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "build_index.py"))

    assert (data_dir / "normalized").exists() is False
    assert (data_dir / "structured").exists() is False
    assert (data_dir / "chunks").exists() is False
    assert (data_dir / "index").exists() is False

    assert corpus_module["main"]() == 0

    summary = index_module["build_indexes"](
        data_dir / "chunks",
        data_dir / "index",
        embedder=FakeEmbedder(),
        vector_store_factory=RecordingVectorStore,
    )

    assert (data_dir / "normalized").exists()
    assert (data_dir / "structured").exists()
    assert (data_dir / "chunks").exists()
    assert (data_dir / "index").exists()
    assert len(list((data_dir / "normalized").glob("*.txt"))) == 2
    assert len(list((data_dir / "structured").glob("*.json"))) == 2
    assert len(list((data_dir / "chunks").glob("*.jsonl"))) == 2
    assert summary["chunk_count"] > 0
    assert summary["keyword_db"] == data_dir / "index" / "retrieval.db"
    assert summary["vector_index"] == data_dir / "index" / "faiss.index"
    assert summary["vector_map"] == data_dir / "index" / "vector_map.json"

    vector_map = json.loads(summary["vector_map"].read_text(encoding="utf-8"))
    assert len(vector_map) == summary["chunk_count"]
    assert {item["document_id"] for item in vector_map} == {
        "hebei_xiaofang_tiaoli",
        "xiaofangfa_2019",
    }
