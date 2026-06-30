from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
from typing import Literal


MANIFEST_VERSION = 1


class ManifestConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class IncrementalImportRecord:
    document_id: str
    source_name: str
    source_path: str
    source_sha256: str
    chunk_count: int
    run_id: str
    status: Literal["committed"]
    imported_at: str


@dataclass(frozen=True)
class IncrementalImportManifest:
    version: int
    imports: list[IncrementalImportRecord]


def load_manifest(path: Path) -> IncrementalImportManifest:
    if not path.exists():
        return IncrementalImportManifest(version=MANIFEST_VERSION, imports=[])

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("manifest 不是合法 JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("manifest 结构不合法")
    if payload.get("version") != MANIFEST_VERSION:
        raise ValueError("manifest version 不受支持")
    imports_payload = payload.get("imports")
    if not isinstance(imports_payload, list):
        raise ValueError("manifest imports 结构不合法")

    records: list[IncrementalImportRecord] = []
    for item in imports_payload:
        if not isinstance(item, dict):
            raise ValueError("manifest imports 结构不合法")
        try:
            if item["status"] != "committed":
                raise ValueError("manifest imports 结构不合法")
            records.append(
                IncrementalImportRecord(
                    document_id=str(item["document_id"]),
                    source_name=str(item["source_name"]),
                    source_path=str(item["source_path"]),
                    source_sha256=str(item["source_sha256"]),
                    chunk_count=int(item["chunk_count"]),
                    run_id=str(item["run_id"]),
                    status="committed",
                    imported_at=str(item["imported_at"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("manifest imports 结构不合法") from exc

    return IncrementalImportManifest(version=MANIFEST_VERSION, imports=records)


def append_import_record(
    manifest_path: Path,
    *,
    document_id: str,
    source_name: str,
    source_path: str,
    source_sha256: str,
    chunk_count: int,
    run_id: str,
) -> IncrementalImportManifest:
    manifest = load_manifest(manifest_path)
    if any(item.document_id == document_id for item in manifest.imports):
        raise ManifestConflictError(f"manifest 已记录 document_id: {document_id}")

    updated = IncrementalImportManifest(
        version=MANIFEST_VERSION,
        imports=[
            *manifest.imports,
            IncrementalImportRecord(
                document_id=document_id,
                source_name=source_name,
                source_path=source_path,
                source_sha256=source_sha256,
                chunk_count=chunk_count,
                run_id=run_id,
                status="committed",
                imported_at=datetime.now(UTC).isoformat(),
            ),
        ],
    )
    _write_manifest_atomically(manifest_path, updated)
    return updated


def _write_manifest_atomically(path: Path, manifest: IncrementalImportManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": manifest.version,
        "imports": [asdict(item) for item in manifest.imports],
    }
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
