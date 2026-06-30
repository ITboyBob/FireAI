from hashlib import sha256
from pathlib import Path
from dataclasses import replace as dataclass_replace

import re
import pytest

from app.services.chunk_builder import build_intermediate_chunks
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
    MetadataEvidence,
    SourceSpan,
    TargetMetadata,
)
from app.services.legal_quality_gates import (
    GateOutcome,
    QualityInput,
    QualityReport,
    _gate_s2_leading_material_isolation,
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


def _s2_source_and_extraction(tmp_path: Path):
    source = _source(tmp_path, title="某规定")
    lines = (
        "某省人民政府",
        "关于修订《某规定》的决定",
        "某规定",
        "（2020年1月1日公布）",
        "第一条 正文一。",
        "第二条 正文二。",
    )
    return source, _extraction(source, lines)


def _s2_intermediate(
    source: SourceRef,
    extraction: ExtractionResult,
    *,
    revision_events: tuple[str, ...] = ("关于修订《某规定》的决定",),
    issuing_authority: str | None = "某省人民政府",
    promulgated_on: str | None = "2020年1月1日",
    effective_on: str | None = None,
    version_basis: str | None = None,
    evidence_status: str = "confirmed",
    omit_evidence: set[str] | None = None,
) -> LegalDocumentIntermediate:
    blocks = extraction.text_blocks
    title_index = 2
    title_unit = BodyUnit(
        unit_id="u-title",
        kind="title",
        text="某规定",
        source_span=_span(title_index, "某规定"),
    )
    article1 = BodyUnit(
        unit_id="u-1",
        kind="article",
        text="第一条 正文一。",
        source_span=_span(4, "第一条 正文一。"),
        parent_unit_id="u-title",
    )
    article2 = BodyUnit(
        unit_id="u-2",
        kind="article",
        text="第二条 正文二。",
        source_span=_span(5, "第二条 正文二。"),
        parent_unit_id="u-title",
    )
    units = (title_unit, article1, article2)
    boundary_start = blocks[title_index].location
    boundary_end = article2.source_span.end

    omit = omit_evidence or set()
    evidence: list[MetadataEvidence] = []
    if issuing_authority is not None and "issuing_authority" not in omit:
        evidence.append(
            MetadataEvidence(
                field_name="issuing_authority",
                value=issuing_authority,
                source_span=_span(0, blocks[0].text),
                extraction_status=evidence_status,
            )
        )
    if promulgated_on is not None and "promulgated_on" not in omit:
        date_text = promulgated_on
        date_block = blocks[3]
        evidence.append(
            MetadataEvidence(
                field_name="promulgated_on",
                value=date_text,
                source_span=SourceSpan(
                    start=date_block.location,
                    end=date_block.location,
                    start_char_offset=1,
                    end_char_offset=1 + len(date_text),
                ),
                extraction_status=evidence_status,
            )
        )
    if effective_on is not None and "effective_on" not in omit:
        evidence.append(
            MetadataEvidence(
                field_name="effective_on",
                value=effective_on,
                source_span=_span(3, blocks[3].text),
                extraction_status=evidence_status,
            )
        )
    for event in revision_events:
        if "revision_events" not in omit:
            evidence.append(
                MetadataEvidence(
                    field_name="revision_events",
                    value=event,
                    source_span=_span(1, blocks[1].text),
                    extraction_status=evidence_status,
                )
            )

    excluded_ranges = []
    if title_index > 0:
        excluded_ranges.append(
            ExcludedRange(
                source_span=SourceSpan(
                    start=blocks[0].location,
                    end=blocks[title_index - 1].location,
                    start_char_offset=0,
                    end_char_offset=len(blocks[title_index - 1].text),
                ),
                kind="leading_publication_material",
                reason="publication_and_revision_material_before_target_title",
            )
        )

    coverage = SourceSpan(
        start=boundary_start,
        end=boundary_end,
        start_char_offset=0,
        end_char_offset=boundary_end_char_offset(article2.source_span),
    )

    return LegalDocumentIntermediate(
        schema_version="legal-intermediate-v2",
        document_id="doc_example",
        source_ref=source,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S2,
        target=TargetMetadata(
            title="某规定",
            issuing_authority=issuing_authority,
            promulgated_on=promulgated_on,
            effective_on=effective_on,
            revision_events=revision_events,
            version_basis=version_basis,
            evidence=tuple(evidence),
        ),
        boundary=BoundaryDecision(
            status="confirmed",
            start=boundary_start,
            end=boundary_end,
            title_evidence=("expected_title_exact_match:block:2",),
            start_evidence=("first_article:block:4",),
            end_evidence=("continuous_last_article:block:5",),
        ),
        body_text="\n".join(unit.text for unit in units),
        body_units=units,
        diagnostics=(),
        extraction_report=ExtractionReport(
            status="confirmed",
            extractor_kind=ExtractionClass.W.value,
            extractor_version="word-v1",
            excluded_ranges=tuple(excluded_ranges),
            source_coverage=coverage,
        ),
    )


def boundary_end_char_offset(span: SourceSpan) -> int:
    return span.end_char_offset


def _s2_parsed(intermediate: LegalDocumentIntermediate) -> ParsedDocument:
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
        issuing_authority=intermediate.target.issuing_authority,
        region=None,
        promulgated_on=intermediate.target.promulgated_on,
        effective_on=intermediate.target.effective_on,
        articles=articles,
        source_sha256=intermediate.source_ref.source_sha256,
        extraction_class=intermediate.extraction_class.value,
        content_class=intermediate.content_class.value,
        boundary_status=intermediate.boundary.status,
        version_basis=intermediate.target.version_basis,
        revision_events=intermediate.target.revision_events,
        metadata_evidence=intermediate.target.evidence,
    )


def _s2_quality_input(tmp_path: Path, **kwargs) -> QualityInput:
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(source, extraction, **kwargs)
    parsed = _s2_parsed(intermediate)
    chunks = build_intermediate_chunks(intermediate, parsed)
    return QualityInput(
        source_sha256=source.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=intermediate.extraction_class,
        content_class=intermediate.content_class,
        source=source,
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )


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


def test_s2_gates_pass_for_valid_s2(tmp_path):
    quality_input = _s2_quality_input(tmp_path)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.PASS, [
        (g.gate_id, g.outcome, g.reason_code)
        for g in report.gates
        if g.outcome != GateOutcome.PASS
    ]
    gate_ids = {g.gate_id for g in report.gates}
    assert "s2_leading_material_isolation" in gate_ids
    assert "s2_metadata_traceability" in gate_ids
    assert report.ruleset_version == "legal-quality-v2"


def test_s2_missing_leading_exclusion_fails(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(source, extraction)
    intermediate = dataclass_replace(
        intermediate,
        extraction_report=dataclass_replace(
            intermediate.extraction_report,
            excluded_ranges=(),
        ),
    )
    quality_input = _s2_quality_input_from_intermediate(tmp_path, intermediate, extraction)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "s2_leading_material_isolation")
    assert gate.outcome == GateOutcome.FAIL
    assert gate.reason_code == "missing_leading_material_exclusion"


def test_s2_leading_exclusion_overlaps_body_fails(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(source, extraction)
    blocks = extraction.text_blocks
    bad_range = ExcludedRange(
        source_span=SourceSpan(
            start=blocks[0].location,
            end=blocks[2].location,
            start_char_offset=0,
            end_char_offset=len(blocks[2].text),
        ),
        kind="leading_publication_material",
        reason="publication_and_revision_material_before_target_title",
    )
    intermediate = dataclass_replace(
        intermediate,
        extraction_report=dataclass_replace(
            intermediate.extraction_report,
            excluded_ranges=(bad_range,),
        ),
    )
    parsed = _s2_parsed(intermediate)
    quality_input = QualityInput(
        source_sha256=source.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=intermediate.extraction_class,
        content_class=intermediate.content_class,
        source=source,
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=(),
    )

    gate = _gate_s2_leading_material_isolation(quality_input)

    assert gate.outcome == GateOutcome.FAIL
    assert gate.reason_code == "leading_material_overlaps_body"


def test_s2_leading_article_number_contaminates_body_fails(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    blocks = extraction.text_blocks
    intermediate = _s2_intermediate(source, extraction)
    # 把前置材料里的修改决定换成一条独立的“第一条”，模拟附件中的条文混入正文
    contaminated_block_text = "第一条 本规定适用于某领域。"
    contaminated_evidence = tuple(
        dataclass_replace(ev, value=contaminated_block_text)
        if ev.field_name == "revision_events"
        else ev
        for ev in intermediate.target.evidence
    )
    contaminated_target = dataclass_replace(
        intermediate.target,
        revision_events=(contaminated_block_text,),
        evidence=contaminated_evidence,
    )
    contaminated_excluded = ExcludedRange(
        source_span=intermediate.extraction_report.excluded_ranges[0].source_span,
        kind="leading_publication_material",
        reason="publication_and_revision_material_before_target_title",
    )
    intermediate = dataclass_replace(
        intermediate,
        target=contaminated_target,
    )
    extraction = dataclass_replace(
        extraction,
        text_blocks=tuple(
            dataclass_replace(block, text=contaminated_block_text)
            if block.order == 1
            else block
            for block in blocks
        ),
    )
    quality_input = _s2_quality_input_from_intermediate(tmp_path, intermediate, extraction)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "s2_leading_material_isolation")
    assert gate.outcome == GateOutcome.FAIL
    assert gate.reason_code == "leading_article_numbers_in_body"


def test_s2_metadata_without_evidence_requires_review(tmp_path):
    quality_input = _s2_quality_input(
        tmp_path,
        issuing_authority="某省人民政府",
        omit_evidence={"issuing_authority"},
    )

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.REVIEW_REQUIRED
    gate = next(g for g in report.gates if g.gate_id == "s2_metadata_traceability")
    assert gate.outcome == GateOutcome.REVIEW_REQUIRED
    assert gate.reason_code == "metadata_value_without_evidence"


def test_s2_evidence_span_out_of_range_fails(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(source, extraction)
    bad_blocks = extraction.text_blocks
    bad_evidence = tuple(
        dataclass_replace(
            ev,
            source_span=SourceSpan(
                start=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=len(bad_blocks) + 10,
                    line_number=len(bad_blocks) + 11,
                ),
                end=SourceLocation(
                    logical_page=1,
                    page_number=None,
                    block_order=len(bad_blocks) + 10,
                    line_number=len(bad_blocks) + 11,
                ),
                start_char_offset=0,
                end_char_offset=3,
            ),
        )
        if ev.field_name == "issuing_authority"
        else ev
        for ev in intermediate.target.evidence
    )
    bad_target = dataclass_replace(intermediate.target, evidence=bad_evidence)
    intermediate = dataclass_replace(intermediate, target=bad_target)
    quality_input = _s2_quality_input_from_intermediate(tmp_path, intermediate, extraction)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "s2_metadata_traceability")
    assert gate.outcome == GateOutcome.FAIL
    assert gate.reason_code == "evidence_span_invalid"


def test_s2_evidence_value_mismatch_fails(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(source, extraction)
    bad_evidence = tuple(
        dataclass_replace(ev, value="某机关")
        if ev.field_name == "issuing_authority"
        else ev
        for ev in intermediate.target.evidence
    )
    bad_target = dataclass_replace(
        intermediate.target,
        evidence=bad_evidence,
    )
    intermediate = dataclass_replace(intermediate, target=bad_target)
    quality_input = _s2_quality_input_from_intermediate(tmp_path, intermediate, extraction)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.FAIL
    gate = next(g for g in report.gates if g.gate_id == "s2_metadata_traceability")
    assert gate.outcome == GateOutcome.FAIL
    assert gate.reason_code == "evidence_value_mismatch"


def test_s2_revision_signal_without_traceability_requires_review(tmp_path):
    source, extraction = _s2_source_and_extraction(tmp_path)
    intermediate = _s2_intermediate(
        source,
        extraction,
        revision_events=(),
        version_basis=None,
        omit_evidence={"revision_events"},
    )
    quality_input = _s2_quality_input_from_intermediate(tmp_path, intermediate, extraction)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.REVIEW_REQUIRED
    gate = next(g for g in report.gates if g.gate_id == "s2_metadata_traceability")
    assert gate.outcome == GateOutcome.REVIEW_REQUIRED
    assert gate.reason_code == "revision_signal_without_traceability"


def test_s2_multi_authority_without_confirmed_evidence_requires_review(tmp_path):
    quality_input = _s2_quality_input(
        tmp_path,
        issuing_authority="A部；B部",
        evidence_status="review_required",
    )

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.REVIEW_REQUIRED
    gate = next(g for g in report.gates if g.gate_id == "s2_metadata_traceability")
    assert gate.outcome == GateOutcome.REVIEW_REQUIRED
    assert gate.reason_code == "multi_authority_without_confirmed_evidence"


def test_s2_review_or_fail_does_not_produce_qualification(tmp_path):
    quality_input = _s2_quality_input(
        tmp_path,
        issuing_authority="某省人民政府",
        omit_evidence={"issuing_authority"},
    )

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.REVIEW_REQUIRED
    assert all(g.outcome != GateOutcome.FAIL for g in report.gates)


def test_s1_skips_s2_specific_gates_and_remains_pass(tmp_path):
    quality_input = _quality_input(tmp_path)

    report = evaluate_legal_quality(quality_input)

    assert report.overall == GateOutcome.PASS
    gate_ids = {g.gate_id for g in report.gates}
    assert "s2_leading_material_isolation" not in gate_ids
    assert "s2_metadata_traceability" not in gate_ids
    assert report.ruleset_version == "legal-quality-v2"


def _s2_quality_input_from_intermediate(
    tmp_path: Path,
    intermediate: LegalDocumentIntermediate,
    extraction: ExtractionResult,
) -> QualityInput:
    parsed = _s2_parsed(intermediate)
    chunks = build_intermediate_chunks(intermediate, parsed)
    return QualityInput(
        source_sha256=intermediate.source_ref.source_sha256,
        document_id=intermediate.document_id,
        extraction_class=intermediate.extraction_class,
        content_class=intermediate.content_class,
        source=intermediate.source_ref,
        extraction=extraction,
        intermediate=intermediate,
        parsed=parsed,
        chunks=tuple(chunks),
    )
