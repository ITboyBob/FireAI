from pathlib import Path
import subprocess

import pytest

from app.services.corpus_ingestor import CorpusDocument
from app.services.normalizer import (
    NormalizationError,
    clean_text,
    load_document_text,
    normalize_document,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "normalized"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8").rstrip("\n")


def _expected_fire_law() -> str:
    return _read_fixture("expected_fire_law.txt")


def test_clean_text_removes_page_noise():
    raw = (
        "第一章 总则\n\n"
        "HYPERLINK foo\n"
        "第 1 页\n"
        "消防工作贯彻预防为主。\n\n"
    )

    cleaned = clean_text(raw)

    assert "HYPERLINK" not in cleaned
    assert "第 1 页" not in cleaned
    assert cleaned == "第一章 总则\n消防工作贯彻预防为主。"


def test_clean_text_matches_expected_fire_law_fixture():
    raw = (
        "中华人民共和国消防法\n"
        "第一章　总  则\n"
        "HYPERLINK foo\n"
        "第一条　为了预防火灾和减少火灾危害，加强应急救援工作，保护人身、财产安全，维护公共安全，制定本法。\n"
        "第 1 页\n"
        "第二条　消防工作贯彻预防为主、防消结合的方针。\n"
    )

    cleaned = clean_text(raw)

    assert cleaned == _expected_fire_law()


def test_clean_text_strips_inline_hyperlink_field_code_from_real_fixture():
    raw = _read_fixture("inline_hyperlink_raw.txt")
    expected = _read_fixture("inline_hyperlink_expected.txt")

    cleaned = clean_text(raw)

    assert cleaned == expected


def test_clean_text_normalizes_unicode_line_separators():
    raw = "第一条 消防产品应当合格。\u2028第二条 应当予以公布。\u2029第三条 继续执行。"

    cleaned = clean_text(raw)

    assert cleaned == "第一条 消防产品应当合格。\n第二条 应当予以公布。\n第三条 继续执行。"


@pytest.mark.parametrize("suffix", ["doc", "docx"])
def test_load_document_text_uses_textutil_for_word_documents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    suffix: str,
):
    source_path = tmp_path / f"sample.{suffix}"
    source_path.write_text("stub", encoding="utf-8")

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool):
        assert cmd == [
            "/usr/bin/textutil",
            "-convert",
            "txt",
            "-stdout",
            "-encoding",
            "UTF-8",
            str(source_path),
        ]
        assert check is False
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(cmd, 0, stdout="转换结果\n", stderr="")

    monkeypatch.setattr("app.services.normalizer.subprocess.run", fake_run)

    document = CorpusDocument(
        document_id="sample",
        source_path=source_path,
        source_name="sample",
        file_type=suffix,
    )

    assert load_document_text(document) == "转换结果\n"


def test_normalize_document_writes_cleaned_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source_path = tmp_path / "消防法--2019年4月23日.doc"
    source_path.write_text("stub", encoding="utf-8")

    document = CorpusDocument(
        document_id="xiaofangfa_2019",
        source_path=source_path,
        source_name="消防法--2019年4月23日",
        file_type="doc",
    )

    monkeypatch.setattr(
        "app.services.normalizer.load_document_text",
        lambda _: (
            "中华人民共和国消防法\n"
            "第一章　总  则\n"
            "HYPERLINK foo\n"
            "第一条　为了预防火灾和减少火灾危害，加强应急救援工作，保护人身、财产安全，维护公共安全，制定本法。\n"
            "第 1 页\n"
            "第二条　消防工作贯彻预防为主、防消结合的方针。\n"
        ),
    )

    result = normalize_document(document, tmp_path / "data" / "normalized")

    assert result.output_path == tmp_path / "data" / "normalized" / "xiaofangfa_2019.txt"
    assert result.output_path.read_text(encoding="utf-8") == _expected_fire_law()
    assert result.failure_report_path is None
    assert result.error_message is None


def test_normalize_document_writes_failure_report_when_cleaned_text_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    source_path = tmp_path / "empty.doc"
    source_path.write_text("stub", encoding="utf-8")

    document = CorpusDocument(
        document_id="empty_doc",
        source_path=source_path,
        source_name="empty",
        file_type="doc",
    )

    monkeypatch.setattr(
        "app.services.normalizer.load_document_text",
        lambda _: "HYPERLINK foo\n第 1 页\n",
    )

    result = normalize_document(document, tmp_path / "data" / "normalized")

    assert result.output_path is None
    assert result.error_message == "Normalized text is empty after cleaning."
    assert result.failure_report_path == (
        tmp_path / "data" / "normalized" / "empty_doc.error.txt"
    )
    assert result.failure_report_path.read_text(encoding="utf-8") == (
        "document_id: empty_doc\n"
        f"source_path: {source_path}\n"
        "reason: Normalized text is empty after cleaning.\n"
    )


def test_load_document_text_raises_when_textutil_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    source_path = tmp_path / "broken.doc"
    source_path.write_text("stub", encoding="utf-8")

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool):
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="conversion failed",
        )

    monkeypatch.setattr("app.services.normalizer.subprocess.run", fake_run)

    document = CorpusDocument(
        document_id="broken_doc",
        source_path=source_path,
        source_name="broken",
        file_type="doc",
    )

    with pytest.raises(NormalizationError, match="conversion failed"):
        load_document_text(document)
