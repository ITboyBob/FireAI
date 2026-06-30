from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_extractor import SourceLocation
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
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
    validate_legal_intermediate,
    write_confirmed_normalized,
)


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


def _source(tmp_path: Path) -> SourceRef:
    path = tmp_path / "某规定.doc"
    path.write_bytes(b"sample")
    return SourceRef(
        relative_path="某规定.doc",
        source_path=path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )


def _valid_intermediate(tmp_path: Path) -> LegalDocumentIntermediate:
    title = BodyUnit(
        unit_id="unit-0",
        kind="title",
        text="某规定",
        source_span=_span(0, "某规定"),
    )
    article = BodyUnit(
        unit_id="unit-1",
        kind="article",
        text="第一条 正文",
        source_span=_span(1, "第一条 正文"),
    )
    return LegalDocumentIntermediate(
        schema_version="legal-intermediate-v1",
        document_id="doc_example",
        source_ref=_source(tmp_path),
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
        target=TargetMetadata(title="某规定"),
        boundary=BoundaryDecision(
            status="confirmed",
            start=_location(0),
            end=_location(1),
            title_evidence=("expected_title_exact_match:block:0",),
            start_evidence=("first_article:block:1",),
            end_evidence=("continuous_last_article:block:1",),
        ),
        body_text="某规定\n第一条 正文",
        body_units=(title, article),
        diagnostics=(),
        extraction_report=ExtractionReport(
            status="confirmed",
            extractor_kind="W",
            extractor_version="fake-v1",
            excluded_ranges=(),
            warnings=("physical_pagination_unknown",),
            source_coverage=SourceSpan(
                start=_location(0),
                end=_location(1),
                start_char_offset=0,
                end_char_offset=len("第一条 正文"),
            ),
        ),
    )


def test_valid_confirmed_intermediate_writes_only_confirmed_body(tmp_path):
    intermediate = _valid_intermediate(tmp_path)
    output_dir = tmp_path / "staging" / "normalized"

    validate_legal_intermediate(intermediate)
    output_path = write_confirmed_normalized(intermediate, output_dir)

    assert output_path.read_text(encoding="utf-8") == intermediate.body_text
    assert list(output_dir.iterdir()) == [output_path]


def test_non_confirmed_intermediate_cannot_write_or_create_directory(tmp_path):
    source = _source(tmp_path)
    intermediate = LegalDocumentIntermediate(
        schema_version="legal-intermediate-v1",
        document_id="doc_example",
        source_ref=source,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
        target=TargetMetadata(title="某规定"),
        boundary=BoundaryDecision(
            status="review_required",
            start=None,
            end=None,
            ambiguities=("title_not_unique",),
        ),
        body_text="",
        body_units=(),
        diagnostics=("title_not_unique",),
        extraction_report=ExtractionReport(
            status="review_required",
            extractor_kind="W",
            extractor_version="fake-v1",
        ),
    )
    output_dir = tmp_path / "staging" / "normalized"

    validate_legal_intermediate(intermediate)
    with pytest.raises(ValueError, match="confirmed"):
        write_confirmed_normalized(intermediate, output_dir)

    assert not output_dir.exists()


@pytest.mark.parametrize("mutation", ["empty_body", "missing_article", "overlap"])
def test_confirmed_intermediate_rejects_core_invariant_violations(
    tmp_path,
    mutation,
):
    valid = _valid_intermediate(tmp_path)
    kwargs = {
        "schema_version": valid.schema_version,
        "document_id": valid.document_id,
        "source_ref": valid.source_ref,
        "extraction_class": valid.extraction_class,
        "content_class": valid.content_class,
        "target": valid.target,
        "boundary": valid.boundary,
        "body_text": valid.body_text,
        "body_units": valid.body_units,
        "diagnostics": valid.diagnostics,
        "extraction_report": valid.extraction_report,
    }
    if mutation == "empty_body":
        kwargs["body_text"] = ""
    elif mutation == "missing_article":
        kwargs["body_text"] = "某规定"
        kwargs["body_units"] = (valid.body_units[0],)
    else:
        kwargs["extraction_report"] = ExtractionReport(
            status="confirmed",
            extractor_kind="W",
            extractor_version="fake-v1",
            excluded_ranges=(
                ExcludedRange(
                    source_span=_span(1, "第一条 正文"),
                    kind="trailing_noise",
                    reason="test",
                ),
            ),
            source_coverage=valid.extraction_report.source_coverage,
        )

    with pytest.raises(ValueError):
        validate_legal_intermediate(LegalDocumentIntermediate(**kwargs))


def test_intermediate_is_invalid_after_source_digest_changes(tmp_path):
    intermediate = _valid_intermediate(tmp_path)
    intermediate.source_ref.source_path.write_bytes(b"changed")

    with pytest.raises(ValueError, match="摘要"):
        validate_legal_intermediate(intermediate)


def test_metadata_evidence_requires_known_field_and_non_empty_value():
    span = _span(0, "示例文本")

    evidence = MetadataEvidence(
        field_name="promulgated_on",
        value="2020-01-01",
        source_span=span,
        extraction_status="confirmed",
    )
    assert evidence.field_name == "promulgated_on"

    with pytest.raises(ValueError, match="字段名"):
        MetadataEvidence(
            field_name="",
            value="2020-01-01",
            source_span=span,
            extraction_status="confirmed",
        )

    with pytest.raises(ValueError, match="不支持"):
        MetadataEvidence(
            field_name="unknown_field",
            value="2020-01-01",
            source_span=span,
            extraction_status="confirmed",
        )

    with pytest.raises(ValueError, match="值不能为空"):
        MetadataEvidence(
            field_name="effective_on",
            value="",
            source_span=span,
            extraction_status="confirmed",
        )

    with pytest.raises(ValueError, match="状态"):
        MetadataEvidence(
            field_name="version_basis",
            value="2020-01-01",
            source_span=span,
            extraction_status="unknown",
        )


def test_target_metadata_carries_evidence_tuple():
    span = _span(0, "示例文本")
    evidence = MetadataEvidence(
        field_name="issuing_authority",
        value="河北省人民政府",
        source_span=span,
        extraction_status="confirmed",
    )
    target = TargetMetadata(title="河北省消防设施管理规定", evidence=(evidence,))

    assert len(target.evidence) == 1
    assert target.evidence[0].value == "河北省人民政府"


def test_target_metadata_rejects_non_evidence_in_evidence():
    with pytest.raises(ValueError, match="只能包含 MetadataEvidence"):
        TargetMetadata(title="某规定", evidence=("not evidence",))  # type: ignore[arg-type]
