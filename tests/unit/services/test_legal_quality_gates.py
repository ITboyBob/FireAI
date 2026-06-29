from hashlib import sha256
from pathlib import Path
from dataclasses import replace as dataclass_replace

import re
import pytest

from app.services.chunk_builder import build_intermediate_chunks
from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    SourceRef,
)
from app.services.legal_intermediate import (
    BodyUnit,
    BoundaryDecision,
    ExcludedRange,
    ExtractionReport,
    LegalDocumentIntermediate,
    SourceSpan,
    TargetMetadata,
)
from app.services.legal_quality_gates import (
    GateOutcome,
    QualityInput,
    QualityReport,
    evaluate_legal_quality,
)
from app.services.structure_parser import ParsedArticle, ParsedDocument


def _location(order: int) -> SourceLocation:
    return SourceLocation(
        logical_page=1,
        page_number=None,
        block_order=order,
        line_number=order + 1,
    )


def _span(order: int, text: str) -> SourceSpan:
    location = _location(order)
    return SourceSpan(
        start=location,
        end=location,
        start_char_offset=0,
        end_char_offset=len(text),
    )


def _source(tmp_path: Path, title: str = "某规定") -> SourceRef:
    path = tmp_path / f"{title}.doc"
    path.write_bytes(b"sample")
    return SourceRef(
        relative_path=f"{title}.doc",
        source_path=path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )


def _blocks(lines: tuple[str, ...]) -> tuple[ExtractedBlock, ...]:
    return tuple(
        ExtractedBlock(
            order=order,
            text=line,
            location=_location(order),
        )
        for order, line in enumerate(lines)
    )


def _extraction(source: SourceRef, lines: tuple[str, ...]) -> ExtractionResult:
    blocks = _blocks(lines)
    return ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind=ExtractionClass.W.value,
        extractor_version="word-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=tuple(range(len(blocks))),
            ),
        ),
        text_blocks=blocks,
        disposition=IngestionDisposition.READY,
    )


def _intermediate(source: SourceRef, units: tuple[BodyUnit, ...]) -> LegalDocumentIntermediate:
    title = units[0].text
    boundary_start = units[0].source_span.start
    boundary_end = units[-1].source_span.end
    end_char_offset = units[-1].source_span.end_char_offset
    coverage = SourceSpan(
        start=boundary_start,
        end=boundary_end,
        start_char_offset=0,
        end_char_offset=end_char_offset,
    )
    return LegalDocumentIntermediate(
        schema_version="legal-intermediate-v1",
        document_id="doc_example",
        source_ref=source,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
        target=TargetMetadata(title=title),
        boundary=BoundaryDecision(
            status="confirmed",
            start=boundary_start,
            end=boundary_end,
            title_evidence=("expected_title_exact_match:block:0",),
            start_evidence=("first_article:block:1",),
            end_evidence=("continuous_last_article:block:2",),
        ),
        body_text="\n".join(unit.text for unit in units),
        body_units=units,
        diagnostics=(),
        extraction_report=ExtractionReport(
            status="confirmed",
            extractor_kind=ExtractionClass.W.value,
            extractor_version="word-v1",
            excluded_ranges=(),
            source_coverage=coverage,
        ),
    )


def _units(title: str = "某规定", article_texts: tuple[str, ...] = ("第一条 正文",)) -> tuple[BodyUnit, ...]:
    units: list[BodyUnit] = [
        BodyUnit(
            unit_id="unit-0",
            kind="title",
            text=title,
            source_span=_span(0, title),
        ),
    ]
    for index, text in enumerate(article_texts, start=1):
        units.append(
            BodyUnit(
                unit_id=f"unit-{index}",
                kind="article",
                text=text,
                source_span=_span(index, text),
                parent_unit_id="unit-0",
            )
        )
    return tuple(units)


def _parsed(intermediate: LegalDocumentIntermediate) -> ParsedDocument:
    articles = [
        ParsedArticle(
            article_no=unit.text.split()[0],
            chapter_title=None,
            heading_path=(),
            text=unit.text.split(None, 1)[1] if " " in unit.text else "",
            source_span=unit.source_span,
        )
        for unit in intermediate.body_units
        if unit.kind == "article"
    ]
    return ParsedDocument(
        document_id=intermediate.document_id,
        title=intermediate.target.title,
        issuing_authority=None,
        region=None,
        promulgated_on=None,
        effective_on=None,
        articles=articles,
        source_sha256=intermediate.source_ref.source_sha256,
        extraction_class=intermediate.extraction_class.value,
        content_class=intermediate.content_class.value,
        boundary_status=intermediate.boundary.status,
        version_basis=intermediate.target.version_basis,
    )


def _chunks(parsed: ParsedDocument) -> list[dict]:
    structured = {
        "document_id": parsed.document_id,
        "title": parsed.title,
        "articles": [
            {
                "article_no": article.article_no,
                "chapter_title": article.chapter_title,
                "heading_path": list(article.heading_path),
                "text": article.text,
            }
            for article in parsed.articles
        ],
    }
    from app.services.chunk_builder import build_chunks

    return build_chunks(structured, max_chunk_chars=300)


def _quality_input(tmp_path: Path) -> QualityInput:
    source = _source(tmp_path)
    lines = (
        "某规定",
        "第一条 正文",
    )
    extraction = _extraction(source, lines)
    units = _units()
    intermediate = _intermediate(source, units)
    parsed = _parsed(intermediate)
    chunks = _chunks(parsed)
    return QualityInput(
        source_sha256=source.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
        source=source,
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )


def test_evaluate_legal_quality_returns_report_with_all_gate_results(tmp_path):
    quality_input = _quality_input(tmp_path)
    report = evaluate_legal_quality(quality_input)
    assert isinstance(report, QualityReport)
    assert report.overall == GateOutcome.PASS
    gate_ids = {gate.gate_id for gate in report.gates}
    assert "source_identity" in gate_ids
    assert "boundary_confirmed" in gate_ids
    assert "article_start" in gate_ids
    assert "article_numbers" in gate_ids
    assert "article_non_empty" in gate_ids
    assert "body_purity" in gate_ids
    assert "exclusion_isolation" in gate_ids
    assert "cross_layer_consistency" in gate_ids
    assert "chunk_coverage" in gate_ids


def test_source_digest_mismatch_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    quality_input = quality_input.replace(
        source_sha256="0" * 64,
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "source_identity")
    assert gate.outcome == GateOutcome.FAIL


def test_document_id_mismatch_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    quality_input = quality_input.replace(
        document_id="other-doc",
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL


def test_non_confirmed_boundary_requires_review(tmp_path):
    quality_input = _quality_input(tmp_path)
    intermediate = quality_input.intermediate
    new_boundary = BoundaryDecision(
        status="review_required",
        start=None,
        end=None,
        ambiguities=("trailing_content_ambiguous",),
    )
    new_extraction_report = dataclass_replace(
        intermediate.extraction_report,
        status="review_required",
        source_coverage=None,
    )
    new_intermediate = dataclass_replace(
        intermediate,
        boundary=new_boundary,
        body_text="",
        body_units=(),
        extraction_report=new_extraction_report,
    )
    quality_input = quality_input.replace(intermediate=new_intermediate)
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.REVIEW_REQUIRED
    gate = next(g for g in report.gates if g.gate_id == "boundary_confirmed")
    assert gate.outcome == GateOutcome.REVIEW_REQUIRED


def test_missing_first_article_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    source = quality_input.source
    lines = (
        "某规定",
        "第二章 分则",
    )
    extraction = _extraction(source, lines)
    units = _units(article_texts=("第二章 分则",))
    intermediate = _intermediate(source, units)
    parsed = _parsed(intermediate)
    chunks = _chunks(parsed)
    quality_input = quality_input.replace(
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "article_start")
    assert gate.outcome == GateOutcome.FAIL


def test_duplicate_article_numbers_require_review(tmp_path):
    quality_input = _quality_input(tmp_path)
    source = quality_input.source
    lines = (
        "某规定",
        "第一条 正文一",
        "第一条 正文二",
    )
    extraction = _extraction(source, lines)
    units = _units(article_texts=("第一条 正文一", "第一条 正文二"))
    intermediate = _intermediate(source, units)
    parsed = _parsed(intermediate)
    chunks = _chunks(parsed)
    quality_input = quality_input.replace(
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.REVIEW_REQUIRED
    gate = next(g for g in report.gates if g.gate_id == "article_numbers")
    assert gate.outcome == GateOutcome.REVIEW_REQUIRED


def test_page_field_in_body_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    source = quality_input.source
    lines = (
        "某规定",
        "第一条 正文 PAGE \\* MERGEFORMAT",
    )
    extraction = _extraction(source, lines)
    units = _units(article_texts=("第一条 正文 PAGE \\* MERGEFORMAT",))
    intermediate = _intermediate(source, units)
    parsed = _parsed(intermediate)
    chunks = _chunks(parsed)
    quality_input = quality_input.replace(
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "body_purity")
    assert gate.outcome == GateOutcome.FAIL


def test_cross_layer_inconsistent_title_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    parsed = quality_input.parsed
    new_parsed = dataclass_replace(parsed, title="篡改标题")
    quality_input = quality_input.replace(parsed=new_parsed)
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "cross_layer_consistency")
    assert gate.outcome == GateOutcome.FAIL


def test_missing_chunk_for_article_fails(tmp_path):
    quality_input = _quality_input(tmp_path)
    quality_input = quality_input.replace(chunks=())
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "chunk_coverage")
    assert gate.outcome == GateOutcome.FAIL


def test_cross_layer_article_with_paragraph_children_passes(tmp_path):
    """article 单元只保存条号与首段，后续段落作为 paragraph 子单元存在时，
    cross_layer_consistency 应把子单元拼接后再与 parsed 全文比较。"""
    source = _source(tmp_path)
    title = "某规定"
    article1 = "第一条 首段正文"
    paragraph1 = "第二条后的续段正文。"
    units = (
        BodyUnit(
            unit_id="unit-0",
            kind="title",
            text=title,
            source_span=_span(0, title),
        ),
        BodyUnit(
            unit_id="unit-1",
            kind="article",
            text=article1,
            source_span=_span(1, article1),
            parent_unit_id="unit-0",
        ),
        BodyUnit(
            unit_id="unit-2",
            kind="paragraph",
            text=paragraph1,
            source_span=_span(2, paragraph1),
            parent_unit_id="unit-1",
        ),
    )
    intermediate = _intermediate(source, units)
    parsed = _parsed_with_paragraphs(intermediate)
    chunks = _chunks(parsed)
    quality_input = QualityInput(
        source_sha256=source.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=intermediate.extraction_class,
        content_class=intermediate.content_class,
        source=source,
        extraction=_extraction(source, (title, article1, paragraph1)),
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
    report = evaluate_legal_quality(quality_input)
    assert report.overall == GateOutcome.PASS, [
        (g.gate_id, g.outcome, g.reason_code) for g in report.gates if g.outcome != GateOutcome.PASS
    ]


def _parsed_with_paragraphs(intermediate: LegalDocumentIntermediate) -> ParsedDocument:
    article_units = [u for u in intermediate.body_units if u.kind == "article"]
    children_by_parent = {}
    for unit in intermediate.body_units:
        if unit.kind == "paragraph" and unit.parent_unit_id:
            children_by_parent.setdefault(unit.parent_unit_id, []).append(unit)

    bound_articles = []
    for article_unit in article_units:
        match = re.match(r"^(第[一二三四五六七八九十百千万零〇两]+条)\s*(.*)$", article_unit.text)
        if match is None:
            raise ValueError(f"article 单元格式错误: {article_unit.text}")
        body = match.group(2).strip()
        for child in children_by_parent.get(article_unit.unit_id, []):
            body = f"{body}\n{child.text}".strip() if body else child.text.strip()
        bound_articles.append(
            ParsedArticle(
                article_no=match.group(1),
                chapter_title=None,
                heading_path=(),
                text=body,
                source_span=article_unit.source_span,
            )
        )

    return ParsedDocument(
        document_id=intermediate.document_id,
        title=intermediate.target.title,
        issuing_authority=None,
        region=None,
        promulgated_on=None,
        effective_on=None,
        articles=bound_articles,
        source_sha256=intermediate.source_ref.source_sha256,
        extraction_class=intermediate.extraction_class.value,
        content_class=intermediate.content_class.value,
        boundary_status=intermediate.boundary.status,
        version_basis=intermediate.target.version_basis,
    )
