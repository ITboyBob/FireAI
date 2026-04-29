import json
from pathlib import Path
import shutil

import pytest

from app.services.incremental_import import run_incremental_import
from app.services.keyword_index import search_keyword_index
from app.services.vector_index import load_vector_map
from tests.integration.pipeline.test_build_pipeline import FakeEmbedder
from tests.integration.pipeline.test_incremental_import_pipeline import (
    _build_existing_corpus_and_index,
)


def test_incremental_import_real_docx_smoke(tmp_path):
    old_source = Path("法律文本") / "河北省消防条例.docx"
    new_source = Path("法律文本") / "河北省火灾高危单位消防安全管理规定.docx"
    if not old_source.exists() or not new_source.exists():
        pytest.skip("本机缺少真实 docx 法律文本")

    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True)
    shutil.copy2(old_source, raw_dir / old_source.name)
    copied_new_source = tmp_path / new_source.name
    shutil.copy2(new_source, copied_new_source)

    _build_existing_corpus_and_index(raw_dir=raw_dir, data_dir=data_dir)

    summary = run_incremental_import(
        sources=[copied_new_source],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="run-real-smoke",
    )

    document_id = summary.committed_document_ids[0]
    normalized_path = data_dir / "normalized" / f"{document_id}.txt"
    structured_path = data_dir / "structured" / f"{document_id}.json"
    chunks_path = data_dir / "chunks" / f"{document_id}.jsonl"

    normalized = normalized_path.read_text(encoding="utf-8")
    assert "HYPERLINK" not in normalized
    assert "http://" not in normalized
    assert "https://" not in normalized
    assert '\\l "#"' not in normalized

    structured = json.loads(structured_path.read_text(encoding="utf-8"))
    assert structured["articles"]

    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert chunks
    assert search_keyword_index("火灾高危单位", data_dir / "index" / "retrieval.db", top_k=5)

    vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
    assert [item["position"] for item in vector_map] == list(range(len(vector_map)))

    manifest = json.loads((data_dir / "manifests" / "incremental_imports.json").read_text(encoding="utf-8"))
    assert [item["document_id"] for item in manifest["imports"]] == [document_id]
