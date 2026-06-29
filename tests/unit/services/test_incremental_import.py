import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from app.services.corpus_ingestor import CorpusDocument
from app.services.incremental_import import (
    CommitPlan,
    commit_staged_import,
    create_import_staging,
    generate_new_corpus_artifacts,
    IncrementalImportError,
    resolve_explicit_sources,
    run_incremental_import,
    validate_append_only_preflight,
)
from app.services.incremental_manifest import append_import_record
from app.services.keyword_index import build_keyword_index
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ContentSignals,
    ExtractionClass,
    IngestionDisposition,
    LegalSourceClassification,
    LegalSourceRecord,
    SourceProbe,
)
from app.services.legal_strategy_registry import (
    build_boundary_strategy_registry,
    build_extraction_strategy_registry,
)


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


def test_generate_new_corpus_artifacts_writes_only_to_staging(
    tmp_path: Path,
    monkeypatch,
):
    document = CorpusDocument(
        document_id="new_fire_rule",
        source_path=tmp_path / "新消防规定.docx",
        source_name="新消防规定",
        file_type="docx",
    )
    document.source_path.write_text("placeholder", encoding="utf-8")
    staging = create_import_staging(tmp_path / "data" / ".staging", run_id="run-123")

    def fake_normalize_document(document, output_dir):
        output_path = output_dir / f"{document.document_id}.txt"
        output_path.write_text("新消防规定\n第一条 新增法规正文。", encoding="utf-8")
        return type("Result", (), {"output_path": output_path, "error_message": None})()

    monkeypatch.setattr(
        "app.services.incremental_import.normalize_document",
        fake_normalize_document,
    )

    result = generate_new_corpus_artifacts([document], staging)

    assert (staging.normalized_dir / "new_fire_rule.txt").exists()
    assert (staging.structured_dir / "new_fire_rule.json").exists()
    assert (staging.chunks_dir / "new_fire_rule.jsonl").exists()
    assert result[0].document_id == "new_fire_rule"
    assert result[0].chunk_count > 0
    assert not (tmp_path / "data" / "chunks" / "new_fire_rule.jsonl").exists()


def test_commit_staged_import_does_not_publish_partial_corpus_files(
    tmp_path: Path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")
    _prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    _prepare_existing_fake_vector_index(index_dir, document_id="old_doc", vector_count=1)
    _write_staged_new_doc_files(staging, document_id="new_doc")

    def fail_keyword_append(*args, **kwargs):
        raise IncrementalImportError("模拟关键词索引失败")

    monkeypatch.setattr(
        "app.services.incremental_import.append_keyword_index",
        fail_keyword_append,
    )

    with pytest.raises(IncrementalImportError, match="模拟关键词索引失败"):
        commit_staged_import(
            _commit_plan(
                document_id="new_doc",
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
            ),
            embedder=object(),
        )

    assert not (data_dir / "normalized" / "new_doc.txt").exists()
    assert not (data_dir / "structured" / "new_doc.json").exists()
    assert not (data_dir / "chunks" / "new_doc.jsonl").exists()
    assert not manifest_path.exists()


def test_commit_staged_import_keeps_formal_keyword_db_unchanged_when_later_step_fails(
    tmp_path: Path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")

    _prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    _prepare_existing_fake_vector_index(index_dir, document_id="old_doc", vector_count=1)
    keyword_count_before = _count_keyword_rows(index_dir / "retrieval.db")
    _write_staged_new_doc_files(staging, document_id="new_doc")

    def fail_vector_append(*args, **kwargs):
        raise IncrementalImportError("模拟向量索引失败")

    monkeypatch.setattr(
        "app.services.incremental_import.append_vector_index",
        fail_vector_append,
    )

    with pytest.raises(IncrementalImportError, match="模拟向量索引失败"):
        commit_staged_import(
            _commit_plan(
                document_id="new_doc",
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
            ),
            embedder=object(),
        )

    assert _count_keyword_rows(index_dir / "retrieval.db") == keyword_count_before
    assert not _keyword_document_exists(index_dir / "retrieval.db", "new_doc")


def test_commit_staged_import_rolls_back_everything_when_manifest_write_fails(
    tmp_path: Path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")

    _prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    _prepare_existing_fake_vector_index(index_dir, document_id="old_doc", vector_count=1)
    _write_staged_new_doc_files(staging, document_id="new_doc")

    keyword_count_before = _count_keyword_rows(index_dir / "retrieval.db")
    vector_count_before = _read_fake_vector_count(index_dir / "faiss.index")
    vector_map_before = (index_dir / "vector_map.json").read_text(encoding="utf-8")
    manifest_before = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else None

    def fake_vector_append(chunks, output_dir, **kwargs):
        (output_dir / "faiss.index").write_text("fake-vector-count=2", encoding="utf-8")
        vector_map = json.loads((output_dir / "vector_map.json").read_text(encoding="utf-8"))
        vector_map.append({"position": 1, **chunks[0]})
        (output_dir / "vector_map.json").write_text(
            json.dumps(vector_map, ensure_ascii=False),
            encoding="utf-8",
        )
        return object()

    def fail_manifest_append(*args, **kwargs):
        raise IncrementalImportError("模拟 manifest 写入失败")

    monkeypatch.setattr(
        "app.services.incremental_import.append_vector_index",
        fake_vector_append,
    )
    monkeypatch.setattr(
        "app.services.incremental_import.append_import_record",
        fail_manifest_append,
    )

    with pytest.raises(IncrementalImportError, match="模拟 manifest 写入失败"):
        commit_staged_import(
            _commit_plan(
                document_id="new_doc",
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
            ),
            embedder=object(),
        )

    assert _count_keyword_rows(index_dir / "retrieval.db") == keyword_count_before
    assert not _keyword_document_exists(index_dir / "retrieval.db", "new_doc")
    assert _read_fake_vector_count(index_dir / "faiss.index") == vector_count_before
    assert (index_dir / "vector_map.json").read_text(encoding="utf-8") == vector_map_before
    assert not (data_dir / "normalized" / "new_doc.txt").exists()
    assert not (data_dir / "structured" / "new_doc.json").exists()
    assert not (data_dir / "chunks" / "new_doc.jsonl").exists()
    if manifest_before is None:
        assert not manifest_path.exists()
    else:
        assert manifest_path.read_text(encoding="utf-8") == manifest_before


def test_run_incremental_import_returns_committed_summary(tmp_path: Path, monkeypatch):
    source = tmp_path / "新消防规定.docx"
    source.write_text("placeholder", encoding="utf-8")
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    _prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    _prepare_existing_fake_vector_index(index_dir, document_id="old_doc", vector_count=1)

    classifier = _fake_classifier(ContentClass.S1)
    extraction_registry = build_extraction_strategy_registry(
        word_extractor=_FakeWordExtractor()
    )
    boundary_registry = build_boundary_strategy_registry(
        s1_strategy=S1BoundaryStrategy()
    )

    def fake_vector_append(chunks, output_dir, **kwargs):
        (output_dir / "faiss.index").write_text("fake-vector-count=2", encoding="utf-8")
        vector_map = json.loads((output_dir / "vector_map.json").read_text(encoding="utf-8"))
        vector_map.append({"position": len(vector_map), **chunks[0]})
        (output_dir / "vector_map.json").write_text(
            json.dumps(vector_map, ensure_ascii=False),
            encoding="utf-8",
        )
        return object()

    monkeypatch.setattr(
        "app.services.incremental_import.append_vector_index",
        fake_vector_append,
    )

    summary = run_incremental_import(
        sources=[source],
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=object(),
        run_id="run-123",
        classifier=classifier,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    assert summary.run_id == "run-123"
    assert len(summary.committed_document_ids) == 1
    document_id = summary.committed_document_ids[0]
    assert summary.documents[0].document_id == document_id
    assert summary.total_chunks > 0
    assert (data_dir / "normalized" / f"{document_id}.txt").exists()
    assert (data_dir / "structured" / f"{document_id}.json").exists()
    assert (data_dir / "chunks" / f"{document_id}.jsonl").exists()
    assert summary.manifest_path.exists()


def test_run_incremental_import_rejects_unsupported_extraction_class(tmp_path: Path):
    source = tmp_path / "新消防规定.docx"
    source.write_text("placeholder", encoding="utf-8")

    def classifier(source_ref):
        return _fake_source_record(source_ref, extraction_class=ExtractionClass.PT)

    extraction_registry = build_extraction_strategy_registry()
    boundary_registry = build_boundary_strategy_registry(s1_strategy=S1BoundaryStrategy())

    with pytest.raises(IncrementalImportError, match="unsupported"):
        run_incremental_import(
            sources=[source],
            data_dir=tmp_path / "data",
            index_dir=tmp_path / "data" / "index",
            manifest_path=tmp_path / "data" / "manifests" / "incremental_imports.json",
            staging_root=tmp_path / "data" / ".staging",
            embedder=object(),
            run_id="run-123",
            classifier=classifier,
            extraction_registry=extraction_registry,
            boundary_registry=boundary_registry,
        )


def _fake_classifier(content_class: ContentClass):
    def classifier(source_ref: SourceRef) -> LegalSourceRecord:
        return _fake_source_record(source_ref, content_class=content_class)

    return classifier


def _fake_source_record(
    source_ref: SourceRef,
    *,
    extraction_class: ExtractionClass = ExtractionClass.W,
    content_class: ContentClass = ContentClass.S1,
) -> LegalSourceRecord:
    return LegalSourceRecord(
        source=source_ref,
        probe=SourceProbe(
            source_sha256=source_ref.source_sha256,
            signature_kind="wordprocessingml",
            detected_mime_type=None,
            declared_extension=source_ref.declared_extension,
            readable=True,
        ),
        classification=LegalSourceClassification(
            extraction_class=extraction_class,
            content_class=content_class,
            disposition=ClassificationDisposition.READY,
            evidence=ClassificationEvidence(
                source_sha256=source_ref.source_sha256,
                signature_kind="wordprocessingml",
                detected_mime_type=None,
                declared_extension=source_ref.declared_extension,
                conversion_succeeded=True,
                converted_character_count=42,
            ),
            content_signals=ContentSignals(
                candidate_extracted=True,
                title_count=1,
                article_marker_count=1,
            ),
        ),
    )


@dataclass(frozen=True)
class _FakeWordExtractor:
    kind: str = ExtractionClass.W.value
    version: str = "fake-v1"

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        title = request.source.source_path.stem
        blocks = (
            ExtractedBlock(
                order=0,
                text=title,
                location=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=0,
                    line_number=None,
                ),
            ),
            ExtractedBlock(
                order=1,
                text="第一条 新增法规正文。",
                location=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=1,
                    line_number=None,
                ),
            ),
        )
        return ExtractionResult(
            source_sha256=request.source.source_sha256,
            extractor_kind=self.kind,
            extractor_version=self.version,
            pages=(
                ExtractedPage(
                    logical_page=1,
                    page_number=None,
                    block_orders=(0, 1),
                ),
            ),
            text_blocks=blocks,
            disposition=IngestionDisposition.READY,
        )


def _new_fire_rule_document(tmp_path: Path) -> CorpusDocument:
    source_path = tmp_path / "新消防规定.docx"
    source_path.write_text("placeholder", encoding="utf-8")
    return CorpusDocument(
        document_id="new_fire_rule",
        source_path=source_path,
        source_name="新消防规定",
        file_type="docx",
    )


def _commit_plan(
    *,
    document_id: str,
    staging,
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
) -> CommitPlan:
    return CommitPlan(
        document_id=document_id,
        source_name="新法规",
        source_path="/tmp/new.docx",
        source_file_type="docx",
        chunk_count=1,
        staging=staging,
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=manifest_path,
        run_id="run-123",
    )


def _write_staged_new_doc_files(staging, *, document_id: str) -> None:
    (staging.normalized_dir / f"{document_id}.txt").write_text(
        "新法规\n第一条 新增消防安全责任。",
        encoding="utf-8",
    )
    (staging.structured_dir / f"{document_id}.json").write_text("{}", encoding="utf-8")
    (staging.chunks_dir / f"{document_id}.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "new-1",
                "document_id": document_id,
                "title": "新法规",
                "path": "新法规 > 第一条",
                "text": "新增消防安全责任。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _prepare_existing_keyword_db(db_path: Path, *, document_id: str) -> None:
    build_keyword_index(
        [
            {
                "chunk_id": "old-1",
                "document_id": document_id,
                "title": "旧法规",
                "path": "旧法规 > 第一条",
                "text": "旧消防设施要求。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        db_path,
    )


def _prepare_existing_fake_vector_index(
    index_dir: Path,
    *,
    document_id: str,
    vector_count: int,
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "faiss.index").write_text(
        f"fake-vector-count={vector_count}",
        encoding="utf-8",
    )
    (index_dir / "vector_map.json").write_text(
        json.dumps(
            [
                {
                    "position": 0,
                    "chunk_id": "old-1",
                    "document_id": document_id,
                    "text": "旧消防设施要求。",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _count_keyword_rows(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])


def _keyword_document_exists(db_path: Path, document_id: str) -> bool:
    with sqlite3.connect(db_path) as connection:
        return (
            connection.execute(
                "SELECT 1 FROM chunks WHERE document_id = ? LIMIT 1",
                (document_id,),
            ).fetchone()
            is not None
        )


def _read_fake_vector_count(index_path: Path) -> int:
    payload = index_path.read_text(encoding="utf-8")
    return int(payload.split("=", maxsplit=1)[1])
