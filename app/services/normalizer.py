from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from app.services.corpus_ingestor import CorpusDocument


TEXTUTIL_BINARY = "/usr/bin/textutil"
STRUCTURE_HEADING_PATTERN = re.compile(
    r"^(第[一二三四五六七八九十百千万零〇两]+[编章节])\s*(.*)$"
)
ARTICLE_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千万零〇两]+条)\s*(.*)$")
PAGE_NOISE_PATTERN = re.compile(r"^第\s*\d+\s*页$")
INLINE_HYPERLINK_PATTERN = re.compile(
    r'\s*HYPERLINK\s+"[^"]+"\s+(?:\\l\s+"[^"]+"\s+)?'
)


class NormalizationError(RuntimeError):
    """Raised when a source document cannot be normalized into usable text."""


@dataclass(frozen=True)
class NormalizationResult:
    document_id: str
    source_path: Path
    output_path: Path | None
    failure_report_path: Path | None
    error_message: str | None


def clean_text(raw: str) -> str:
    text = (
        raw.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\ufeff", "")
        .replace("\x0c", "\n")
        .replace("\u2028", "\n")
        .replace("\u2029", "\n")
        .replace("\u00a0", " ")
        .replace("\u3000", " ")
    )

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("HYPERLINK") or PAGE_NOISE_PATTERN.fullmatch(line):
            continue

        line = _strip_inline_hyperlink_fields(line)
        line = re.sub(r"[ \t]+", " ", line)
        line = _normalize_heading_spacing(line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def load_document_text(document: CorpusDocument) -> str:
    result = subprocess.run(
        [
            TEXTUTIL_BINARY,
            "-convert",
            "txt",
            "-stdout",
            "-encoding",
            "UTF-8",
            str(document.source_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "textutil conversion failed"
        raise NormalizationError(stderr)

    return result.stdout


def normalize_document(document: CorpusDocument, output_dir: Path) -> NormalizationResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        cleaned = clean_text(load_document_text(document))
        if not cleaned:
            raise NormalizationError("Normalized text is empty after cleaning.")

        output_path = output_dir / f"{document.document_id}.txt"
        output_path.write_text(cleaned, encoding="utf-8")
        return NormalizationResult(
            document_id=document.document_id,
            source_path=document.source_path,
            output_path=output_path,
            failure_report_path=None,
            error_message=None,
        )
    except (NormalizationError, OSError) as exc:
        failure_report_path = output_dir / f"{document.document_id}.error.txt"
        failure_report_path.write_text(
            "\n".join(
                [
                    f"document_id: {document.document_id}",
                    f"source_path: {document.source_path}",
                    f"reason: {exc}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return NormalizationResult(
            document_id=document.document_id,
            source_path=document.source_path,
            output_path=None,
            failure_report_path=failure_report_path,
            error_message=str(exc),
        )


def _normalize_heading_spacing(line: str) -> str:
    structure_match = STRUCTURE_HEADING_PATTERN.match(line)
    if structure_match:
        prefix, title = structure_match.groups()
        compact_title = re.sub(r"\s+", "", title)
        return f"{prefix} {compact_title}".strip()

    article_match = ARTICLE_PATTERN.match(line)
    if article_match:
        prefix, body = article_match.groups()
        return f"{prefix} {body.strip()}".strip()

    return line


def _strip_inline_hyperlink_fields(line: str) -> str:
    return INLINE_HYPERLINK_PATTERN.sub("", line)
