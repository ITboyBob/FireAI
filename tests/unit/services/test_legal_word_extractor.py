from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_extractor import ExtractionRequest
from app.services.legal_ingestion_models import (
    ClassificationEvidence,
    ExtractionClass,
    IngestionDisposition,
    SourceRef,
)
from app.services.legal_textutil import TextutilRunResult
from app.services.legal_word_extractor import WordLegalExtractor


def _request(tmp_path: Path, *, extraction_class=ExtractionClass.W):
    source_path = tmp_path / "sample.doc"
    source_path.write_bytes(b"sample")
    digest = sha256(b"sample").hexdigest()
    return ExtractionRequest(
        source=SourceRef(
            relative_path="sample.doc",
            source_path=source_path,
            source_sha256=digest,
            size_bytes=6,
            declared_extension=".doc",
        ),
        extraction_class=extraction_class,
        classification_evidence=ClassificationEvidence(
            source_sha256=digest,
            signature_kind="ole_doc",
            detected_mime_type="application/msword",
            declared_extension=".doc",
            conversion_succeeded=True,
            converted_character_count=20,
        ),
        run_id="run-123",
    )


def _tree(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    )


def test_word_extractor_preserves_line_blank_and_block_order_without_writing(tmp_path):
    request = _request(tmp_path)
    candidate = (
        "某规定\n\n第一条 正文\nPAGE \\* MERGEFORMAT\n"
        "列一\t列二\t列三"
    )
    calls = []

    def fake_textutil(source_path):
        calls.append(source_path)
        return TextutilRunResult(returncode=0, stdout=candidate, stderr="")

    before = _tree(tmp_path)
    result = WordLegalExtractor(run_textutil=fake_textutil).extract(request)

    assert calls == [request.source.source_path]
    assert result.disposition is IngestionDisposition.READY
    assert [block.text for block in result.text_blocks] == [
        "某规定",
        "",
        "第一条 正文",
        "PAGE \\* MERGEFORMAT",
        "列一\t列二\t列三",
    ]
    assert [block.order for block in result.text_blocks] == [0, 1, 2, 3, 4]
    assert [block.location.line_number for block in result.text_blocks] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert result.pages[0].logical_page == 1
    assert result.pages[0].page_number is None
    assert "physical_pagination_unknown" in result.warnings
    assert "word_page_field" in result.warnings
    assert "possible_table_linearization" in result.warnings
    assert not hasattr(result, "output_path")
    assert before == _tree(tmp_path)


@pytest.mark.parametrize(
    ("textutil_result", "expected_code"),
    [
        (
            TextutilRunResult(
                returncode=1,
                stdout="",
                stderr="conversion failed",
            ),
            "textutil_failed",
        ),
        (
            TextutilRunResult(returncode=0, stdout="", stderr=""),
            "empty_text",
        ),
        (
            TextutilRunResult(returncode=0, stdout="某规定\ufffd第一条", stderr=""),
            "text_decode_failed",
        ),
    ],
)
def test_word_extractor_returns_structured_failure(
    tmp_path,
    textutil_result,
    expected_code,
):
    request = _request(tmp_path)
    extractor = WordLegalExtractor(run_textutil=lambda source: textutil_result)

    result = extractor.extract(request)

    assert result.disposition is IngestionDisposition.FAILED
    assert result.failure.code == expected_code
    assert result.pages == ()
    assert result.text_blocks == ()


def test_word_extractor_rejects_non_w_request(tmp_path):
    request = _request(tmp_path, extraction_class=ExtractionClass.PT)

    with pytest.raises(ValueError, match="W"):
        WordLegalExtractor(
            run_textutil=lambda source: TextutilRunResult(
                returncode=0,
                stdout="某规定\n第一条 正文",
                stderr="",
            )
        ).extract(request)


def test_word_extractor_fails_when_source_digest_changes(tmp_path):
    request = _request(tmp_path)

    def mutating_textutil(source_path):
        source_path.write_bytes(b"changed")
        return TextutilRunResult(
            returncode=0,
            stdout="某规定\n第一条 正文",
            stderr="",
        )

    result = WordLegalExtractor(run_textutil=mutating_textutil).extract(request)

    assert result.disposition is IngestionDisposition.FAILED
    assert result.failure.code == "source_changed"
