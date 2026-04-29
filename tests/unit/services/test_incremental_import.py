from pathlib import Path

import pytest

from app.services.incremental_import import IncrementalImportError, resolve_explicit_sources


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
