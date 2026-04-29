import json
import runpy
import sqlite3
from pathlib import Path

from app.services.incremental_import import run_incremental_import
from app.services.keyword_index import search_keyword_index
from app.services.vector_index import load_vector_map
from tests.integration.pipeline.test_build_pipeline import (
    FakeEmbedder,
    MINI_FIRE_LAW,
    _write_docx,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_incremental_import_appends_new_law_without_losing_existing_index(tmp_path):
    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True)
    _write_docx(MINI_FIRE_LAW, raw_dir / "消防法--2019年4月23日.docx")

    new_source = tmp_path / "新增消防规定.docx"
    _write_docx("新增消防规定\n第一条 新增消防设施维护要求。", new_source)

    _build_existing_corpus_and_index(raw_dir=raw_dir, data_dir=data_dir)

    summary = run_incremental_import(
        sources=[new_source],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="run-append",
    )

    assert summary.total_chunks > 0
    assert search_keyword_index("国家实行消防安全责任制", data_dir / "index" / "retrieval.db", top_k=5)
    assert search_keyword_index("新增消防设施维护要求", data_dir / "index" / "retrieval.db", top_k=5)

    vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
    positions = [item["position"] for item in vector_map]
    assert positions == list(range(len(vector_map)))
    assert summary.committed_document_ids[0] in {item["document_id"] for item in vector_map}

    manifest = json.loads((data_dir / "manifests" / "incremental_imports.json").read_text(encoding="utf-8"))
    assert [item["document_id"] for item in manifest["imports"]] == summary.committed_document_ids


def _build_existing_corpus_and_index(*, raw_dir: Path, data_dir: Path) -> None:
    corpus_module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "build_corpus.py"))
    index_module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "build_index.py"))

    import os

    old_raw = os.environ.get("RAW_CORPUS_DIR")
    old_data = os.environ.get("DATA_DIR")
    try:
        os.environ["RAW_CORPUS_DIR"] = str(raw_dir)
        os.environ["DATA_DIR"] = str(data_dir)
        assert corpus_module["main"]() == 0
    finally:
        if old_raw is None:
            os.environ.pop("RAW_CORPUS_DIR", None)
        else:
            os.environ["RAW_CORPUS_DIR"] = old_raw
        if old_data is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = old_data

    index_module["build_indexes"](
        data_dir / "chunks",
        data_dir / "index",
        embedder=FakeEmbedder(),
    )


def _count_keyword_rows(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])
