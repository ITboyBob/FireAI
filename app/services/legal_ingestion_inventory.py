from hashlib import sha256
import json
from pathlib import Path

from app.services.legal_ingestion_models import FrozenBatchInput, SourceRef


class LegalIngestionInventoryError(RuntimeError):
    pass


def freeze_batch_input(root: Path) -> FrozenBatchInput:
    resolved_root = Path(root).expanduser().resolve()
    if not resolved_root.exists():
        raise LegalIngestionInventoryError(f"批次根目录不存在: {resolved_root}")
    if not resolved_root.is_dir():
        raise LegalIngestionInventoryError(f"批次根路径不是目录: {resolved_root}")

    source_paths = _discover_source_paths(resolved_root)
    if not source_paths:
        raise LegalIngestionInventoryError("批次根目录中没有业务文件")

    sources = tuple(
        _freeze_source(resolved_root, source_path) for source_path in source_paths
    )
    return FrozenBatchInput(
        root=resolved_root,
        sources=sources,
        batch_digest=_build_batch_digest(sources),
    )


def _discover_source_paths(root: Path) -> tuple[Path, ...]:
    discovered: list[Path] = []
    for path in root.rglob("*"):
        if path.name == ".DS_Store":
            continue
        if path.is_symlink():
            raise LegalIngestionInventoryError(f"批次来源不能是符号链接: {path}")
        if path.is_file():
            discovered.append(path)

    return tuple(
        sorted(
            discovered,
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )


def _freeze_source(root: Path, source_path: Path) -> SourceRef:
    try:
        before = source_path.stat()
        content = source_path.read_bytes()
        after = source_path.stat()
    except OSError as exc:
        raise LegalIngestionInventoryError(f"读取批次来源失败: {source_path}") from exc

    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or after.st_size != len(content)
    ):
        raise LegalIngestionInventoryError(f"来源在读取期间发生变化: {source_path}")

    return SourceRef(
        relative_path=source_path.relative_to(root).as_posix(),
        source_path=source_path.resolve(),
        source_sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
        declared_extension=source_path.suffix.lower(),
    )


def _build_batch_digest(sources: tuple[SourceRef, ...]) -> str:
    canonical_sources = [
        {
            "relative_path": source.relative_path,
            "source_sha256": source.source_sha256,
            "size_bytes": source.size_bytes,
            "declared_extension": source.declared_extension,
        }
        for source in sources
    ]
    encoded = json.dumps(
        canonical_sources,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
