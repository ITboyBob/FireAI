from collections.abc import Sequence
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import shutil
import sqlite3
from typing import TYPE_CHECKING, Literal, cast
import uuid

from app.services.chunk_builder import build_chunks, write_chunks
from app.services.corpus_ingestor import CorpusDocument, build_document_id
from app.services.incremental_manifest import append_import_record, load_manifest
from app.services.keyword_index import append_keyword_index
from app.services.normalizer import normalize_document
from app.services.structure_parser import parse_legal_document, write_structured_document
from app.services.vector_index import append_vector_index

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.services.legal_ingestion_models import LegalSourceRecord, SourceRef
    from app.services.legal_strategy_registry import (
        BoundaryStrategyRegistry,
        ExtractionStrategyRegistry,
    )


class IncrementalImportError(RuntimeError):
    pass


class IncrementalImportRollbackError(IncrementalImportError):
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


@dataclass(frozen=True)
class CommitPlan:
    document_id: str
    source_name: str
    source_path: str
    source_file_type: Literal["doc", "docx"]
    chunk_count: int
    staging: ImportStaging
    data_dir: Path
    index_dir: Path
    manifest_path: Path
    run_id: str


@dataclass(frozen=True)
class CommittedImport:
    document_id: str
    chunk_count: int


@dataclass(frozen=True)
class IncrementalImportSummary:
    run_id: str
    documents: list[CorpusDocument]
    committed_document_ids: list[str]
    total_chunks: int
    manifest_path: Path


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


def run_incremental_import(
    *,
    sources: Sequence[Path],
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
    staging_root: Path,
    embedder: object,
    run_id: str | None = None,
    classifier: "Callable[[SourceRef], LegalSourceRecord] | None" = None,
    extraction_registry: "ExtractionStrategyRegistry | None" = None,
    boundary_registry: "BoundaryStrategyRegistry | None" = None,
) -> IncrementalImportSummary:
    """保留兼容签名的单文件/批次导入入口，内部委托统一编排器。

    新增的三个可选参数用于测试注入 fake 策略；生产调用无需传入。
    """
    from app.services.legal_ingestion_orchestrator import run_legal_ingestion

    return run_legal_ingestion(
        sources=sources,
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=manifest_path,
        staging_root=staging_root,
        embedder=embedder,
        run_id=run_id,
        classifier=classifier,
        extraction_registry=extraction_registry,
        boundary_registry=boundary_registry,
    )

    return IncrementalImportSummary(
        run_id=actual_run_id,
        documents=list(documents),
        committed_document_ids=[item.document_id for item in committed],
        total_chunks=sum(item.chunk_count for item in committed),
        manifest_path=manifest_path,
    )


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


def commit_staged_import(plan: CommitPlan, *, embedder: object) -> CommittedImport:
    document = CorpusDocument(
        document_id=plan.document_id,
        source_path=Path(plan.source_path),
        source_name=plan.source_name,
        file_type=plan.source_file_type,
    )
    validate_append_only_preflight(
        [document],
        data_dir=plan.data_dir,
        index_dir=plan.index_dir,
        manifest_path=plan.manifest_path,
    )

    chunks = _load_staged_chunks(plan.staging.chunks_dir / f"{plan.document_id}.jsonl")

    staged_keyword_db = plan.staging.index_dir / "retrieval.db"
    staged_faiss_index = plan.staging.index_dir / "faiss.index"
    staged_vector_map = plan.staging.index_dir / "vector_map.json"
    _copy_required_file(plan.index_dir / "retrieval.db", staged_keyword_db)
    _copy_required_file(plan.index_dir / "faiss.index", staged_faiss_index)
    _copy_required_file(plan.index_dir / "vector_map.json", staged_vector_map)

    append_keyword_index(chunks, staged_keyword_db, document_id=plan.document_id)
    append_vector_index(
        chunks,
        plan.staging.index_dir,
        embedder=embedder,
        document_id=plan.document_id,
    )

    validate_append_only_preflight(
        [document],
        data_dir=plan.data_dir,
        index_dir=plan.index_dir,
        manifest_path=plan.manifest_path,
    )

    published_corpus_files: list[Path] = []
    index_backups: list[tuple[Path, Path]] = []
    manifest_snapshot = _read_optional_bytes(plan.manifest_path)

    try:
        for staged_file, target_file in _corpus_publish_pairs(plan):
            _publish_exclusive(staged_file, target_file)
            published_corpus_files.append(target_file)

        for staged_file, target_file in (
            (staged_keyword_db, plan.index_dir / "retrieval.db"),
            (staged_faiss_index, plan.index_dir / "faiss.index"),
            (staged_vector_map, plan.index_dir / "vector_map.json"),
        ):
            _replace_with_backup(
                staged_file,
                target_file,
                run_id=plan.run_id,
                backups=index_backups,
            )

        append_import_record(
            plan.manifest_path,
            document_id=plan.document_id,
            source_name=plan.source_name,
            source_path=plan.source_path,
            chunk_count=plan.chunk_count,
            run_id=plan.run_id,
        )
    except Exception:
        _rollback_committed_paths(
            plan=plan,
            published_corpus_files=published_corpus_files,
            index_backups=index_backups,
            manifest_snapshot=manifest_snapshot,
        )
        raise

    for _, backup_path in index_backups:
        if backup_path.exists():
            backup_path.unlink()
    shutil.rmtree(plan.staging.root, ignore_errors=True)
    return CommittedImport(document_id=plan.document_id, chunk_count=plan.chunk_count)


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


def _load_staged_chunks(path: Path) -> list[dict]:
    if not path.exists():
        raise IncrementalImportError(f"staging chunks 不存在: {path}")

    chunks: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            payload = line.strip()
            if payload:
                item = json.loads(payload)
                if not isinstance(item, dict):
                    raise ValueError("chunk row must be an object")
                chunks.append(item)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise IncrementalImportError(f"staging chunks 不合法: {path}") from exc

    if not chunks:
        raise IncrementalImportError(f"staging chunks 为空: {path}")
    return chunks


def _copy_required_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise IncrementalImportError(f"正式索引产物不存在: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _corpus_publish_pairs(plan: CommitPlan) -> tuple[tuple[Path, Path], ...]:
    return (
        (
            plan.staging.normalized_dir / f"{plan.document_id}.txt",
            plan.data_dir / "normalized" / f"{plan.document_id}.txt",
        ),
        (
            plan.staging.structured_dir / f"{plan.document_id}.json",
            plan.data_dir / "structured" / f"{plan.document_id}.json",
        ),
        (
            plan.staging.chunks_dir / f"{plan.document_id}.jsonl",
            plan.data_dir / "chunks" / f"{plan.document_id}.jsonl",
        ),
    )


def _publish_exclusive(staged_file: Path, target_file: Path) -> None:
    if not staged_file.exists():
        raise IncrementalImportError(f"staged corpus file 不存在: {staged_file}")

    target_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with staged_file.open("rb") as source, target_file.open("xb") as target:
            shutil.copyfileobj(source, target)
    except FileExistsError as exc:
        raise IncrementalImportError(f"正式输出文件已存在: {target_file}") from exc


def _replace_with_backup(
    staged_file: Path,
    target_file: Path,
    *,
    run_id: str,
    backups: list[tuple[Path, Path]],
) -> None:
    if not staged_file.exists():
        raise IncrementalImportError(f"staged index file 不存在: {staged_file}")
    if not target_file.exists():
        raise IncrementalImportError(f"正式索引产物不存在: {target_file}")

    backup_path = target_file.with_name(f".{target_file.name}.{run_id}.bak")
    if backup_path.exists():
        raise IncrementalImportError(f"索引备份文件已存在: {backup_path}")

    target_file.replace(backup_path)
    try:
        staged_file.replace(target_file)
    except Exception:
        if target_file.exists():
            target_file.unlink()
        backup_path.replace(target_file)
        raise
    backups.append((target_file, backup_path))


def _read_optional_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _rollback_committed_paths(
    *,
    plan: CommitPlan,
    published_corpus_files: list[Path],
    index_backups: list[tuple[Path, Path]],
    manifest_snapshot: bytes | None,
) -> None:
    rollback_errors: list[str] = []

    for path in published_corpus_files:
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            rollback_errors.append(f"{path}: {exc}")

    for target_path, backup_path in reversed(index_backups):
        try:
            if target_path.exists():
                target_path.unlink()
            if backup_path.exists():
                backup_path.replace(target_path)
        except OSError as exc:
            rollback_errors.append(f"{target_path}: {exc}")

    try:
        if manifest_snapshot is None:
            if plan.manifest_path.exists():
                plan.manifest_path.unlink()
        else:
            plan.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            plan.manifest_path.write_bytes(manifest_snapshot)
    except OSError as exc:
        rollback_errors.append(f"{plan.manifest_path}: {exc}")

    if rollback_errors:
        raise IncrementalImportRollbackError(
            "增量导入回滚失败，请人工核对或恢复以下路径: "
            f"{plan.index_dir / 'retrieval.db'}, "
            f"{plan.index_dir / 'faiss.index'}, "
            f"{plan.index_dir / 'vector_map.json'}, "
            f"{plan.data_dir / 'normalized' / (plan.document_id + '.txt')}, "
            f"{plan.data_dir / 'structured' / (plan.document_id + '.json')}, "
            f"{plan.data_dir / 'chunks' / (plan.document_id + '.jsonl')}, "
            f"{plan.manifest_path}. 回滚错误: {'; '.join(rollback_errors)}"
        )
