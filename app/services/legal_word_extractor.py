from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
import re

from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionFailure,
    ExtractionRequest,
    ExtractionResult,
    SourceLocation,
    validate_extraction_result,
)
from app.services.legal_ingestion_models import (
    ExtractionClass,
    IngestionDisposition,
)
from app.services.legal_textutil import TextutilRunResult, run_textutil_stdout


PAGE_FIELD_PATTERN = re.compile(r"(?:PAGE|MERGEFORMAT)")
PAGE_LINE_PATTERN = re.compile(r"^第\s*\d+\s*页$")


class WordLegalExtractor:
    kind = ExtractionClass.W.value
    version = "word-textutil-v1"

    def __init__(
        self,
        *,
        run_textutil: Callable[[Path], TextutilRunResult] = run_textutil_stdout,
    ) -> None:
        self._run_textutil = run_textutil

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        if request.extraction_class is not ExtractionClass.W:
            raise ValueError("WordLegalExtractor 只接受 W 提取请求")
        if _source_digest(request) != request.source.source_sha256:
            return self._failure(request, code="source_changed", message="来源摘要已变化")

        try:
            converted = self._run_textutil(request.source.source_path)
        except Exception:
            return self._failure(
                request,
                code="textutil_exception",
                message="textutil 执行异常",
            )
        if converted.returncode != 0:
            return self._failure(
                request,
                code="textutil_failed",
                message="textutil 返回非零退出码",
            )
        if not converted.stdout:
            return self._failure(
                request,
                code="empty_text",
                message="textutil 未返回候选文本",
            )
        if "\ufffd" in converted.stdout or "\x00" in converted.stdout:
            return self._failure(
                request,
                code="text_decode_failed",
                message="候选文本包含不可解码字符",
            )
        if _source_digest(request) != request.source.source_sha256:
            return self._failure(request, code="source_changed", message="来源摘要已变化")

        lines = tuple(converted.stdout.splitlines())
        if not lines:
            return self._failure(
                request,
                code="empty_text",
                message="textutil 未返回可定位文本行",
            )
        blocks = tuple(
            ExtractedBlock(
                order=order,
                text=line,
                location=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=order,
                    line_number=order + 1,
                ),
            )
            for order, line in enumerate(lines)
        )
        warnings = ["physical_pagination_unknown"]
        if any(PAGE_FIELD_PATTERN.search(line) for line in lines):
            warnings.append("word_page_field")
        if any(PAGE_LINE_PATTERN.fullmatch(line.strip()) for line in lines):
            warnings.append("possible_header_footer")
        if any("\t" in line for line in lines):
            warnings.append("possible_table_linearization")

        result = ExtractionResult(
            source_sha256=request.source.source_sha256,
            extractor_kind=self.kind,
            extractor_version=self.version,
            pages=(
                ExtractedPage(
                    logical_page=1,
                    page_number=None,
                    block_orders=tuple(range(len(blocks))),
                ),
            ),
            text_blocks=blocks,
            metrics=(
                ("returncode", converted.returncode),
                ("character_count", len(converted.stdout)),
                ("line_count", len(lines)),
                ("empty_line_count", sum(not line for line in lines)),
            ),
            warnings=tuple(warnings),
            disposition=IngestionDisposition.READY,
        )
        validate_extraction_result(request, result)
        return result

    def _failure(
        self,
        request: ExtractionRequest,
        *,
        code: str,
        message: str,
    ) -> ExtractionResult:
        result = ExtractionResult(
            source_sha256=request.source.source_sha256,
            extractor_kind=self.kind,
            extractor_version=self.version,
            pages=(),
            text_blocks=(),
            disposition=IngestionDisposition.FAILED,
            failure=ExtractionFailure(
                stage="extraction",
                code=code,
                message=message,
                retryable=False,
            ),
        )
        validate_extraction_result(request, result)
        return result


def _source_digest(request: ExtractionRequest) -> str:
    try:
        return sha256(request.source.source_path.read_bytes()).hexdigest()
    except OSError:
        return ""
