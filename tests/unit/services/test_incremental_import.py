import json
from pathlib import Path

import pytest

from app.services.corpus_ingestor import CorpusDocument
from app.services.incremental_import import (
    create_import_staging,
    IncrementalImportError,
    resolve_explicit_sources,
    validate_append_only_preflight,
)
from app.services.incremental_manifest import append_import_record
from app.services.keyword_index import build_keyword_index


def test_resolve_explicit_sources_accepts_only_doc_and_docx(tmp_path: Path):
    docx_path = tmp_path / "新消防规定.docx"
    docx_path.write_text("placeholder", encoding="utf-8")
    pdf_path = tmp_path / "新消防规定.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")

    documents = resolve_explicit_sources([docx_path])

    assert documents[0].source_path == docx_path
    assert documents[0].source_name == "新消防规定"
    assert documents[0].file_type == "docx"
    assert documents[0].document_id.startswith("doc_")

    with pytest.raises(IncrementalImportError, match="第一版只支持 .doc/.docx"):
        resolve_explicit_sources([pdf_path])


@pytest.mark.parametrize(
    ("subdir", "suffix"),
    [
        ("normalized", ".txt"),
        ("structured", ".json"),
        ("chunks", ".jsonl"),
    ],
)
def test_preflight_fails_when_formal_output_file_exists(
    tmp_path: Path,
    subdir: str,
    suffix: str,
):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    document = _new_fire_rule_document(tmp_path)
    target_dir = data_dir / subdir
    target_dir.mkdir(parents=True)
    (target_dir / f"{document.document_id}{suffix}").write_text("exists", encoding="utf-8")

    with pytest.raises(IncrementalImportError, match="正式输出文件已存在"):
        validate_append_only_preflight(
            [document],
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifest_path,
        )


def test_preflight_fails_when_manifest_has_document(tmp_path: Path):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    document = _new_fire_rule_document(tmp_path)
    append_import_record(
        manifest_path,
        document_id=document.document_id,
        source_name=document.source_name,
        source_path=str(document.source_path),
        chunk_count=1,
        run_id="run-existing",
    )

    with pytest.raises(IncrementalImportError, match="manifest 已记录"):
        validate_append_only_preflight(
            [document],
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifest_path,
        )


def test_preflight_fails_when_keyword_index_has_document(tmp_path: Path):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    document = _new_fire_rule_document(tmp_path)
    build_keyword_index(
        [
            {
                "chunk_id": "new-1",
                "document_id": document.document_id,
                "title": "新消防规定",
                "path": "新消防规定 > 第一条",
                "text": "新增消防安全责任。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        index_dir / "retrieval.db",
    )

    with pytest.raises(IncrementalImportError, match="关键词索引已有该 document_id"):
        validate_append_only_preflight(
            [document],
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifest_path,
        )


def test_preflight_fails_when_vector_map_has_document(tmp_path: Path):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    document = _new_fire_rule_document(tmp_path)
    index_dir.mkdir(parents=True)
    (index_dir / "vector_map.json").write_text(
        json.dumps(
            [
                {
                    "position": 0,
                    "chunk_id": "new-1",
                    "document_id": document.document_id,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(IncrementalImportError, match="向量映射已有该 document_id"):
        validate_append_only_preflight(
            [document],
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifest_path,
        )


def test_create_import_staging_uses_run_scoped_hidden_directory(tmp_path: Path):
    staging_root = tmp_path / "data" / ".staging"

    staging = create_import_staging(staging_root, run_id="run-123")

    assert staging.root == staging_root / "incremental-import-run-123"
    assert staging.normalized_dir == staging.root / "normalized"
    assert staging.structured_dir == staging.root / "structured"
    assert staging.chunks_dir == staging.root / "chunks"
    assert staging.index_dir == staging.root / "index"
    assert staging.manifest_dir == staging.root / "manifests"
    assert staging.root.exists()


def _new_fire_rule_document(tmp_path: Path) -> CorpusDocument:
    source_path = tmp_path / "新消防规定.docx"
    source_path.write_text("placeholder", encoding="utf-8")
    return CorpusDocument(
        document_id="new_fire_rule",
        source_path=source_path,
        source_name="新消防规定",
        file_type="docx",
    )
