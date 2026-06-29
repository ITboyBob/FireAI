from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
import re
import subprocess
from zipfile import BadZipFile, ZipFile, is_zipfile

from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ClassificationEvidence,
    ContentClass,
    ContentSignals,
    ExtractionClass,
    LegalSourceClassification,
    LegalSourceRecord,
    SourceProbe,
    SourceRef,
)
from app.services.legal_textutil import run_textutil_stdout


FILE_BINARY = "/usr/bin/file"
OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
PDF_SIGNATURE = b"%PDF-"
DOCX_REQUIRED_MEMBERS = frozenset({"[Content_Types].xml", "word/document.xml"})
WORD_MIME_TYPES = {
    "ole_doc": frozenset({"application/msword"}),
    "wordprocessingml": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    ),
}
ARTICLE_PATTERN = re.compile(
    r"^第[一二三四五六七八九十百千万零〇两0-9]+条(?:\s|　|$)"
)
LEGAL_TITLE_PATTERN = re.compile(r".+(?:规定|办法|细则|条例)$")
ATTACHMENT_HEADING_PATTERN = re.compile(
    r"^附件(?:\s|　|[:：]|[一二三四五六七八九十0-9])"
)
LEADING_AUTHORITY_PATTERN = re.compile(
    r"(?:公安部|教育部|民政部|人力资源和社会保障部|住房和城乡建设部|"
    r"文化部|广电总局|安全监管总局|旅游局)"
)
FORM_MARKER_PATTERN = re.compile(r"(?:文书|审批表|决定书|告知书|记录表)")
PAGE_FIELD_PATTERN = re.compile(r"(?:PAGE|MERGEFORMAT)")


def detect_signature(source_path: Path) -> str:
    with source_path.open("rb") as stream:
        prefix = stream.read(max(len(OLE_SIGNATURE), len(PDF_SIGNATURE)))
    if prefix.startswith(OLE_SIGNATURE):
        return "ole_doc"
    if prefix.startswith(PDF_SIGNATURE):
        return "pdf"
    if not is_zipfile(source_path):
        return "unknown"

    try:
        with ZipFile(source_path) as archive:
            members = frozenset(archive.namelist())
    except BadZipFile:
        return "unknown"
    if DOCX_REQUIRED_MEMBERS.issubset(members):
        return "wordprocessingml"
    return "zip"


def detect_mime_type(
    source_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout_seconds: float = 10.0,
) -> str | None:
    result = runner(
        [FILE_BINARY, "--brief", "--mime-type", str(source_path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        return None
    mime_type = result.stdout.strip()
    return mime_type or None


def probe_source(
    source: SourceRef,
    *,
    file_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SourceProbe:
    warnings: list[str] = []
    signature_kind = detect_signature(source.source_path)
    try:
        mime_type = detect_mime_type(source.source_path, runner=file_runner)
    except (OSError, subprocess.SubprocessError):
        mime_type = None
    if mime_type is None:
        warnings.append("mime_probe_failed")

    return SourceProbe(
        source_sha256=source.source_sha256,
        signature_kind=signature_kind,
        detected_mime_type=mime_type,
        declared_extension=source.declared_extension,
        readable=True,
        warnings=tuple(warnings),
    )


def detect_content_signals(candidate_text: str) -> ContentSignals:
    lines = tuple(line.strip() for line in candidate_text.splitlines() if line.strip())
    first_article_index = next(
        (index for index, line in enumerate(lines) if ARTICLE_PATTERN.match(line)),
        None,
    )
    if first_article_index is None:
        return ContentSignals(
            candidate_extracted=bool(candidate_text.strip()),
            title_count=0,
            article_marker_count=0,
            warnings=("article_marker_missing",),
        )

    leading_lines = lines[:first_article_index]
    body_and_tail = lines[first_article_index:]
    title_count = sum(
        1
        for line in leading_lines
        if len(line) <= 80 and LEGAL_TITLE_PATTERN.fullmatch(line)
    )
    article_positions = tuple(
        index
        for index, line in enumerate(body_and_tail)
        if ARTICLE_PATTERN.match(line)
    )
    leading_risk = (
        any("决定" in line or "修订" in line or "修改" in line for line in leading_lines)
        or any(ATTACHMENT_HEADING_PATTERN.match(line) for line in leading_lines)
        or sum(bool(LEADING_AUTHORITY_PATTERN.search(line)) for line in leading_lines) >= 2
    )

    attachment_positions = tuple(
        index
        for index, line in enumerate(body_and_tail)
        if ATTACHMENT_HEADING_PATTERN.match(line)
    )
    first_attachment_index = attachment_positions[0] if attachment_positions else None
    interleaved = (
        first_attachment_index is not None
        and any(index > first_attachment_index for index in article_positions)
    )
    form_marker_count = sum(
        bool(FORM_MARKER_PATTERN.search(line)) for line in body_and_tail
    )
    trailing = (
        first_attachment_index is not None
        and form_marker_count >= 2
        and not interleaved
    )

    warnings: list[str] = []
    if any(PAGE_FIELD_PATTERN.search(line) for line in body_and_tail):
        warnings.append("word_page_field")
    if any("印发" in line for line in body_and_tail):
        warnings.append("trailing_print_info")

    return ContentSignals(
        candidate_extracted=True,
        title_count=title_count,
        article_marker_count=len(article_positions),
        has_leading_material=leading_risk,
        has_trailing_material=trailing,
        has_interleaved_material=interleaved,
        warnings=tuple(warnings),
    )


def classify_content_signals(signals: ContentSignals) -> ContentClass:
    if signals.has_interleaved_material or not signals.candidate_extracted:
        return ContentClass.S4
    if signals.has_leading_material:
        return ContentClass.S2
    if signals.has_trailing_material:
        return ContentClass.S3
    if signals.article_marker_count == 0:
        return ContentClass.S4
    return ContentClass.S1


def classify_source(
    source: SourceRef,
    *,
    file_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    textutil_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> LegalSourceRecord:
    probe = probe_source(source, file_runner=file_runner)
    reason_codes = list(probe.warnings)
    extraction_class = _extraction_class_for_signature(probe.signature_kind)
    content_class: ContentClass | None = None
    content_signals: ContentSignals | None = None
    conversion_succeeded: bool | None = None
    converted_character_count: int | None = None
    disposition = ClassificationDisposition.READY

    if extraction_class is ExtractionClass.PX:
        disposition = ClassificationDisposition.REVIEW_REQUIRED
        reason_codes.append("unresolved_real_format")
    else:
        expected_extension = (
            ".doc" if probe.signature_kind == "ole_doc" else ".docx"
        )
        if source.declared_extension != expected_extension:
            disposition = ClassificationDisposition.REVIEW_REQUIRED
            reason_codes.append("declared_extension_conflict")
        if probe.detected_mime_type not in WORD_MIME_TYPES[probe.signature_kind]:
            disposition = ClassificationDisposition.REVIEW_REQUIRED
            reason_codes.append("mime_type_conflict")

        try:
            conversion = run_textutil_stdout(
                source.source_path,
                runner=textutil_runner,
            )
        except (OSError, subprocess.SubprocessError):
            conversion = None
        if conversion is None or not conversion.succeeded:
            conversion_succeeded = False
            disposition = ClassificationDisposition.REVIEW_REQUIRED
            reason_codes.append("word_conversion_failed")
        else:
            conversion_succeeded = True
            converted_character_count = len(conversion.stdout)
            content_signals = detect_content_signals(conversion.stdout)
            content_class = classify_content_signals(content_signals)
            if not _candidate_is_usable(conversion.stdout, content_signals):
                disposition = ClassificationDisposition.REVIEW_REQUIRED
                reason_codes.append("word_conversion_unusable")
            elif content_class is ContentClass.S4:
                disposition = ClassificationDisposition.REVIEW_REQUIRED
                reason_codes.append("content_structure_ambiguous")

    if _sha256_file(source.source_path) != source.source_sha256:
        disposition = ClassificationDisposition.FAILED
        reason_codes.append("source_changed")

    evidence = ClassificationEvidence(
        source_sha256=source.source_sha256,
        signature_kind=probe.signature_kind,
        detected_mime_type=probe.detected_mime_type,
        declared_extension=source.declared_extension,
        conversion_succeeded=conversion_succeeded,
        converted_character_count=converted_character_count,
        warnings=tuple(dict.fromkeys((*probe.warnings, *(content_signals.warnings if content_signals else ())))),
    )
    classification = LegalSourceClassification(
        extraction_class=extraction_class,
        content_class=content_class,
        disposition=disposition,
        evidence=evidence,
        content_signals=content_signals,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )
    return LegalSourceRecord(
        source=source,
        probe=probe,
        classification=classification,
    )


def _extraction_class_for_signature(signature_kind: str | None) -> ExtractionClass:
    if signature_kind in WORD_MIME_TYPES:
        return ExtractionClass.W
    return ExtractionClass.PX


def _candidate_is_usable(candidate_text: str, signals: ContentSignals) -> bool:
    non_whitespace_count = sum(not character.isspace() for character in candidate_text)
    replacement_count = candidate_text.count("\ufffd")
    return (
        non_whitespace_count >= 8
        and signals.article_marker_count > 0
        and replacement_count / max(len(candidate_text), 1) < 0.02
        and "\x00" not in candidate_text
    )


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
