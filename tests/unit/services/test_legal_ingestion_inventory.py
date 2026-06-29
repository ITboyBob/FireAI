from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_ingestion_inventory import (
    LegalIngestionInventoryError,
    freeze_batch_input,
)


def test_freeze_batch_input_recurses_sorts_and_ignores_only_ds_store(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.docx").write_bytes(b"b")
    (tmp_path / "a.doc").write_bytes(b"a")
    (tmp_path / ".DS_Store").write_bytes(b"noise")
    (nested / "unknown").write_bytes(b"unknown")

    batch = freeze_batch_input(tmp_path)

    assert [item.relative_path for item in batch.sources] == [
        "a.doc",
        "nested/b.docx",
        "nested/unknown",
    ]
    assert [item.declared_extension for item in batch.sources] == [
        ".doc",
        ".docx",
        "",
    ]
    assert batch == freeze_batch_input(tmp_path)


def test_freeze_batch_input_records_absolute_paths_sizes_and_sha256(tmp_path):
    source_path = tmp_path / "sample.docx"
    source_path.write_bytes(b"sample")

    batch = freeze_batch_input(tmp_path)
    source = batch.sources[0]

    assert source.source_path == source_path.resolve()
    assert source.size_bytes == 6
    assert source.source_sha256 == sha256(b"sample").hexdigest()
    assert len(batch.batch_digest) == 64


def test_freeze_batch_input_rejects_missing_empty_and_symlinked_inputs(tmp_path):
    with pytest.raises(LegalIngestionInventoryError, match="不存在"):
        freeze_batch_input(tmp_path / "missing")

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(LegalIngestionInventoryError, match="业务文件"):
        freeze_batch_input(empty)

    real = tmp_path / "real.docx"
    real.write_bytes(b"sample")
    linked_root = tmp_path / "linked"
    linked_root.mkdir()
    (linked_root / "linked.docx").symlink_to(real)
    with pytest.raises(LegalIngestionInventoryError, match="符号链接"):
        freeze_batch_input(linked_root)


def test_freeze_batch_input_detects_source_change_during_hashing(tmp_path, monkeypatch):
    source_path = tmp_path / "sample.docx"
    source_path.write_bytes(b"sample")
    original_read_bytes = Path.read_bytes

    def mutating_read_bytes(path: Path) -> bytes:
        content = original_read_bytes(path)
        if path == source_path:
            path.write_bytes(content + b"-changed")
        return content

    monkeypatch.setattr(Path, "read_bytes", mutating_read_bytes)

    with pytest.raises(LegalIngestionInventoryError, match="读取期间发生变化"):
        freeze_batch_input(tmp_path)
