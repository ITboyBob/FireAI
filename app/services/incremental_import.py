from collections.abc import Sequence
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Literal, cast

from app.services.chunk_builder import build_chunks, write_chunks
from app.services.corpus_ingestor import CorpusDocument, build_document_id
from app.services.incremental_manifest import load_manifest
from app.services.normalizer import normalize_document
from app.services.structure_parser import parse_legal_document, write_structured_document


class IncrementalImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImportStaging:
    root: Path
    normalized_dir: Path
    structured_dir: Path
    chunks_dir: Path
    index_dir: Path
    manifest_dir: Path


@dataclass(frozen=True)
class GeneratedCorpusArtifact:
    document_id: str
    normalized_path: Path
    structured_path: Path
    chunks_path: Path
    chunk_count: int


def resolve_explicit_sources(paths: Sequence[Path]) -> list[CorpusDocument]:
    if not paths:
        raise IncrementalImportError("必须显式指定新增法规文件")

    documents: list[CorpusDocument] = []
    seen_document_ids: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise IncrementalImportError(f"新增法规文件不存在: {path}")
        if path.is_dir():
            raise IncrementalImportError("第一版不支持目录自动扫描")

        file_type = path.suffix.lower().lstrip(".")
        if file_type not in {"doc", "docx"}:
            raise IncrementalImportError("第一版只支持 .doc/.docx 法规文件")

        source_name = path.stem
        document_id = build_document_id(source_name)
        if document_id in seen_document_ids:
            raise IncrementalImportError(f"同一次导入存在重复 document_id: {document_id}")
        seen_document_ids.add(document_id)

        documents.append(
            CorpusDocument(
                document_id=document_id,
                source_path=path,
                source_name=source_name,
                file_type=cast(Literal["doc", "docx"], file_type),
            )
        )

    return documents


def create_import_staging(staging_root: Path, *, run_id: str) -> ImportStaging:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise IncrementalImportError(f"run_id 包含不安全字符: {run_id}")

    root = staging_root / f"incremental-import-{run_id}"
    if root.exists():
        raise IncrementalImportError(f"staging 目录已存在: {root}")

    staging = ImportStaging(
        root=root,
        normalized_dir=root / "normalized",
        structured_dir=root / "structured",
        chunks_dir=root / "chunks",
        index_dir=root / "index",
        manifest_dir=root / "manifests",
    )
    for directory in (
        staging.normalized_dir,
        staging.structured_dir,
        staging.chunks_dir,
        staging.index_dir,
        staging.manifest_dir,
    ):
        directory.mkdir(parents=True, exist_ok=False)
    return staging


def generate_new_corpus_artifacts(
    documents: Sequence[CorpusDocument],
    staging: ImportStaging,
) -> list[GeneratedCorpusArtifact]:
    artifacts: list[GeneratedCorpusArtifact] = []
    for document in documents:
        try:
            normalized = normalize_document(document, staging.normalized_dir)
            if normalized.output_path is None:
                raise IncrementalImportError(
                    f"标准化失败 document_id: {document.document_id}, reason: {normalized.error_message}"
                )

            raw_text = normalized.output_path.read_text(encoding="utf-8")
            parsed = parse_legal_document(document.document_id, raw_text)
            structured_path = write_structured_document(parsed, staging.structured_dir)
            chunks = build_chunks(asdict(parsed))
            if not chunks:
                raise IncrementalImportError(f"chunk 为空 document_id: {document.document_id}")
            chunks_path = write_chunks(chunks, document.document_id, staging.chunks_dir)
        except IncrementalImportError:
            raise
        except Exception as exc:
            raise IncrementalImportError(
                f"新增法规语料生成失败 document_id: {document.document_id}, reason: {exc}"
            ) from exc

        artifacts.append(
            GeneratedCorpusArtifact(
                document_id=document.document_id,
                normalized_path=normalized.output_path,
                structured_path=structured_path,
                chunks_path=chunks_path,
                chunk_count=len(chunks),
            )
        )

    return artifacts


def validate_append_only_preflight(
    documents: Sequence[CorpusDocument],
    *,
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
) -> None:
    manifest = load_manifest(manifest_path)
    manifest_document_ids = {item.document_id for item in manifest.imports}

    for document in documents:
        document_id = document.document_id
        for output_path in _formal_output_paths(data_dir, document_id):
            if output_path.exists():
                raise IncrementalImportError(
                    f"正式输出文件已存在 document_id: {document_id}, path: {output_path}"
                )

        if document_id in manifest_document_ids:
            raise IncrementalImportError(f"manifest 已记录 document_id: {document_id}")

        _ensure_keyword_index_has_no_document(index_dir / "retrieval.db", document_id)
        _ensure_vector_map_has_no_document(index_dir / "vector_map.json", document_id)


def _formal_output_paths(data_dir: Path, document_id: str) -> tuple[Path, Path, Path]:
    return (
        data_dir / "normalized" / f"{document_id}.txt",
        data_dir / "structured" / f"{document_id}.json",
        data_dir / "chunks" / f"{document_id}.jsonl",
    )


def _ensure_keyword_index_has_no_document(db_path: Path, document_id: str) -> None:
    if not db_path.exists():
        return

    try:
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                "SELECT 1 FROM chunks WHERE document_id = ? LIMIT 1",
                (document_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise IncrementalImportError(
            f"关键词索引检查失败 document_id: {document_id}, path: {db_path}"
        ) from exc

    if row is not None:
        raise IncrementalImportError(f"关键词索引已有该 document_id: {document_id}")


def _ensure_vector_map_has_no_document(vector_map_path: Path, document_id: str) -> None:
    if not vector_map_path.exists():
        return

    try:
        vector_map = json.loads(vector_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IncrementalImportError(
            f"向量映射不是合法 JSON document_id: {document_id}, path: {vector_map_path}"
        ) from exc

    if not isinstance(vector_map, list):
        raise IncrementalImportError(f"向量映射结构不合法 path: {vector_map_path}")

    for item in vector_map:
        if isinstance(item, dict) and item.get("document_id") == document_id:
            raise IncrementalImportError(f"向量映射已有该 document_id: {document_id}")
