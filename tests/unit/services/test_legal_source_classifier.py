from hashlib import sha256
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

from app.services.legal_ingestion_inventory import select_scope
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ContentClass,
    ExtractionClass,
    SourceRef,
)
from app.services.legal_source_classifier import (
    classify_content_signals,
    classify_source,
    detect_content_signals,
    detect_signature,
)


def _source_ref(path: Path, *, relative_path: str | None = None) -> SourceRef:
    content = path.read_bytes()
    return SourceRef(
        relative_path=relative_path or path.name,
        source_path=path.resolve(),
        source_sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
        declared_extension=path.suffix.lower(),
    )


def _write_docx(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")


def _file_runner(mime_type: str):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, f"{mime_type}\n", "")

    return run


def _textutil_runner(text: str, *, returncode: int = 0):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            returncode,
            text if returncode == 0 else "",
            "" if returncode == 0 else "conversion failed",
        )

    return run


def test_detect_signature_distinguishes_ole_docx_and_arbitrary_zip(tmp_path):
    ole = tmp_path / "sample.doc"
    ole.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"content")
    docx = tmp_path / "sample.docx"
    _write_docx(docx)
    arbitrary_zip = tmp_path / "fake.docx"
    with ZipFile(arbitrary_zip, "w") as archive:
        archive.writestr("payload.txt", "not word")

    assert detect_signature(ole) == "ole_doc"
    assert detect_signature(docx) == "wordprocessingml"
    assert detect_signature(arbitrary_zip) == "zip"


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("某规定\n第一条 正文\n第二条 正文", ContentClass.S1),
        (
            "关于修改某规定的决定\n附件：某规定\n某规定\n第一条 正文",
            ContentClass.S2,
        ),
        (
            "某规定\n第一条 正文\n第二条 正文\n附件 1\n行政审批表\n处理决定书",
            ContentClass.S3,
        ),
        (
            "某规定\n第一条 正文\n附件 1\n行政审批表\n第二条 正文",
            ContentClass.S4,
        ),
        ("某规定\n第一条 本规定所称附件是配套材料。", ContentClass.S1),
    ],
)
def test_content_signals_conservatively_classify_structure(candidate, expected):
    assert classify_content_signals(detect_content_signals(candidate)) is expected


def test_classify_source_marks_valid_word_ready_without_storing_candidate_text(tmp_path):
    source_path = tmp_path / "sample.doc"
    source_path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"content")
    source = _source_ref(source_path)
    candidate = "某规定\n第一条 正文\n第二条 正文"

    record = classify_source(
        source,
        file_runner=_file_runner("application/msword"),
        textutil_runner=_textutil_runner(candidate),
    )

    assert record.extraction_class is ExtractionClass.W
    assert record.content_class is ContentClass.S1
    assert record.classification.disposition is ClassificationDisposition.READY
    assert record.classification.evidence.converted_character_count == len(candidate)
    assert not hasattr(record, "candidate_text")
    assert candidate not in repr(record)


def test_classify_source_requires_review_for_extension_conflict_and_conversion_failure(
    tmp_path,
):
    disguised_path = tmp_path / "disguised.pdf"
    _write_docx(disguised_path)
    disguised = _source_ref(disguised_path)

    conflict = classify_source(
        disguised,
        file_runner=_file_runner(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        textutil_runner=_textutil_runner("某规定\n第一条 正文"),
    )

    assert conflict.extraction_class is ExtractionClass.W
    assert conflict.classification.disposition is ClassificationDisposition.REVIEW_REQUIRED
    assert "declared_extension_conflict" in conflict.classification.reason_codes

    failed_conversion = classify_source(
        disguised,
        file_runner=_file_runner(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        textutil_runner=_textutil_runner("", returncode=1),
    )

    assert failed_conversion.classification.disposition is (
        ClassificationDisposition.REVIEW_REQUIRED
    )
    assert "word_conversion_failed" in failed_conversion.classification.reason_codes


def test_classify_source_rejects_fake_zip_and_changed_source(tmp_path):
    fake_path = tmp_path / "fake.docx"
    with ZipFile(fake_path, "w") as archive:
        archive.writestr("payload.txt", "not word")
    fake = _source_ref(fake_path)

    fake_record = classify_source(
        fake,
        file_runner=_file_runner("application/zip"),
        textutil_runner=_textutil_runner("某规定\n第一条 正文"),
    )

    assert fake_record.extraction_class is ExtractionClass.PX
    assert fake_record.classification.disposition is (
        ClassificationDisposition.REVIEW_REQUIRED
    )

    source_path = tmp_path / "changed.doc"
    source_path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"content")
    source = _source_ref(source_path)

    def mutating_textutil_runner(args, **kwargs):
        source_path.write_bytes(source_path.read_bytes() + b"-changed")
        return subprocess.CompletedProcess(args, 0, "某规定\n第一条 正文", "")

    changed = classify_source(
        source,
        file_runner=_file_runner("application/msword"),
        textutil_runner=mutating_textutil_runner,
    )

    assert changed.classification.disposition is ClassificationDisposition.FAILED
    assert "source_changed" in changed.classification.reason_codes


def test_select_scope_filters_independent_axes_without_combination_handler(tmp_path):
    source_paths = [tmp_path / "first.doc", tmp_path / "second.doc"]
    for source_path in source_paths:
        source_path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"content")
    first = classify_source(
        _source_ref(source_paths[0]),
        file_runner=_file_runner("application/msword"),
        textutil_runner=_textutil_runner("某规定\n第一条 正文"),
    )
    second = classify_source(
        _source_ref(source_paths[1]),
        file_runner=_file_runner("application/msword"),
        textutil_runner=_textutil_runner(
            "某规定\n第一条 正文\n附件 1\n行政审批表\n处理决定书"
        ),
    )

    selected = select_scope(
        (second, first),
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
    )

    assert selected == (first,)
