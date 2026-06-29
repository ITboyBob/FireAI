from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_extractor import ExtractionRequest
from app.services.legal_ingestion_inventory import freeze_batch_input
from app.services.legal_ingestion_models import (
    ExtractionClass,
    IngestionDisposition,
)
from app.services.legal_source_classifier import classify_source
from app.services.legal_word_extractor import WordLegalExtractor
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.structure_parser import parse_legal_intermediate
from app.services.chunk_builder import build_intermediate_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
REAL_WORD_CASES = (
    (
        "事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx",
        "河北省火灾事故调查处理规定",
    ),
    (
        "督察、处罚与监管/河北省消防技术服务监督管理规定.doc",
        "河北省消防技术服务监督管理规定",
    ),
)
REAL_BOUNDARY_CASES = (
    (
        "事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx",
        "河北省火灾事故调查处理规定",
        27,
    ),
    (
        "督察、处罚与监管/消防监督检查规定.doc",
        "消防监督检查规定",
        40,
    ),
    (
        "督察、处罚与监管/河北省消防技术服务监督管理规定.doc",
        "河北省消防技术服务监督管理规定",
        30,
    ),
    (
        "事故调查、问责与系统治理/河北省消防安全领域信用管理暂行细则.doc",
        "河北省消防安全领域信用管理暂行细则",
        31,
    ),
    (
        "督察、处罚与监管/河北省消防行政执法裁量实施办法.doc",
        "河北省消防行政执法裁量实施办法",
        62,
    ),
)
REAL_PARSED_CASES = (
    (
        "督察、处罚与监管/中华人民共和国消防救援衔条例.docx",
        "中华人民共和国消防救援衔条例",
        26,
        False,
    ),
    (
        "督察、处罚与监管/消防产品监督管理规定.doc",
        "消防产品监督管理规定",
        44,
        False,
    ),
    (
        "事故调查、问责与系统治理/安全生产行政执法与刑事司法衔接工作办法.doc",
        "安全生产行政执法与刑事司法衔接工作办法",
        33,
        True,
    ),
    (
        "事故调查、问责与系统治理/河北省消防安全领域信用管理暂行细则.doc",
        "河北省消防安全领域信用管理暂行细则",
        31,
        False,
    ),
    (
        "事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx",
        "河北省火灾事故调查处理规定",
        27,
        False,
    ),
    (
        "督察、处罚与监管/河北省消防技术服务监督管理规定.doc",
        "河北省消防技术服务监督管理规定",
        30,
        False,
    ),
    (
        "督察、处罚与监管/河北省消防行政执法裁量实施办法.doc",
        "河北省消防行政执法裁量实施办法",
        62,
        False,
    ),
    (
        "督察、处罚与监管/消防监督检查规定.doc",
        "消防监督检查规定",
        40,
        False,
    ),
)


def _relative_tree(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    )


@pytest.mark.parametrize(("relative_path", "expected_title"), REAL_WORD_CASES)
def test_word_extractor_reads_real_ws1_without_persisting_candidate(
    tmp_path,
    relative_path,
    expected_title,
):
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    before_digest = sha256(source.source_path.read_bytes()).hexdigest()
    data_root = PROJECT_ROOT / "data"
    data_before = _relative_tree(data_root)
    temp_before = _relative_tree(tmp_path)
    record = classify_source(source)
    request = ExtractionRequest.from_source_record(record, run_id="real-word")

    result = WordLegalExtractor().extract(request)
    candidate = "\n".join(block.text for block in result.text_blocks)

    assert request.extraction_class is ExtractionClass.W
    assert result.disposition is IngestionDisposition.READY
    assert expected_title in candidate
    assert "第一条" in candidate
    assert result.pages == (
        result.pages[0],
    )
    assert result.pages[0].logical_page == 1
    assert result.pages[0].page_number is None
    assert "physical_pagination_unknown" in result.warnings
    assert before_digest == sha256(source.source_path.read_bytes()).hexdigest()
    assert data_before == _relative_tree(data_root)
    assert temp_before == _relative_tree(tmp_path)


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count"),
    REAL_BOUNDARY_CASES,
)
def test_real_ws1_boundary_covers_clean_and_trailing_risk_samples(
    relative_path,
    expected_title,
    expected_article_count,
):
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    before_digest = sha256(source.source_path.read_bytes()).hexdigest()
    data_root = PROJECT_ROOT / "data"
    data_before = _relative_tree(data_root)
    record = classify_source(source)
    extraction = WordLegalExtractor().extract(
        ExtractionRequest.from_source_record(record, run_id="real-boundary")
    )

    intermediate = S1BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )
    article_units = [
        unit for unit in intermediate.body_units if unit.kind == "article"
    ]

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.body_text.startswith(expected_title)
    assert len(article_units) == expected_article_count
    assert "PAGE \\* MERGEFORMAT" not in intermediate.body_text
    assert before_digest == sha256(source.source_path.read_bytes()).hexdigest()
    assert data_before == _relative_tree(data_root)
    assert all(
        not hasattr(excluded, "text")
        and not hasattr(excluded, "title")
        and not hasattr(excluded, "summary")
        for excluded in intermediate.extraction_report.excluded_ranges
    )


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count", "expect_overlap"),
    REAL_PARSED_CASES,
)
def test_real_ws1_confirmed_body_reaches_parser_and_chunks_without_hiding_risks(
    relative_path,
    expected_title,
    expected_article_count,
    expect_overlap,
):
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    before_digest = sha256(source.source_path.read_bytes()).hexdigest()
    data_root = PROJECT_ROOT / "data"
    data_before = _relative_tree(data_root)
    record = classify_source(source)
    extraction = WordLegalExtractor().extract(
        ExtractionRequest.from_source_record(record, run_id="real-parse")
    )
    intermediate = S1BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )

    parsed = parse_legal_intermediate(intermediate)
    chunks = build_intermediate_chunks(intermediate, parsed)

    assert len(parsed.articles) == expected_article_count
    assert {chunk["article_no"] for chunk in chunks} == {
        article.article_no for article in parsed.articles
    }
    assert all(article.source_span is not None for article in parsed.articles)
    assert all(chunk["source_span"] for chunk in chunks)
    assert all("PAGE \\* MERGEFORMAT" not in chunk["text"] for chunk in chunks)
    if expect_overlap:
        assert parsed.articles[-1].text in parsed.articles[-2].text
    assert before_digest == sha256(source.source_path.read_bytes()).hexdigest()
    assert data_before == _relative_tree(data_root)
