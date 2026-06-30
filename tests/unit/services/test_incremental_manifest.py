from pathlib import Path

import pytest

from app.services.incremental_manifest import (
    IncrementalImportManifest,
    ManifestConflictError,
    append_import_record,
    load_manifest,
)


def test_manifest_append_records_document_once(tmp_path: Path):
    manifest_path = tmp_path / "incremental_imports.json"

    append_import_record(
        manifest_path,
        document_id="new_fire_rule",
        source_name="新消防规定",
        source_path="/tmp/新消防规定.docx",
        source_sha256="a" * 64,
        chunk_count=2,
        run_id="run-1",
    )

    manifest = load_manifest(manifest_path)
    assert isinstance(manifest, IncrementalImportManifest)
    assert [item.document_id for item in manifest.imports] == ["new_fire_rule"]
    assert manifest.imports[0].status == "committed"

    with pytest.raises(ManifestConflictError, match="manifest 已记录"):
        append_import_record(
            manifest_path,
            document_id="new_fire_rule",
            source_name="新消防规定",
            source_path="/tmp/新消防规定.docx",
            source_sha256="a" * 64,
            chunk_count=2,
            run_id="run-2",
        )
