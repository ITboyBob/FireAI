from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.services.legal_extractor import ExtractionRequest
from app.services.legal_ingestion_inventory import freeze_batch_input
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    IngestionInput,
)
from app.services.legal_source_classifier import classify_source
from app.services.legal_word_extractor import WordLegalExtractor
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.legal_s2_boundary import S2BoundaryStrategy
from app.services.legal_ingestion_orchestrator import (
    LegalIngestionOrchestrator,
    build_boundary_strategy_registry,
    build_extraction_strategy_registry,
)
from app.services.legal_intermediate import write_confirmed_normalized
from app.services.structure_parser import parse_legal_intermediate
from app.services.chunk_builder import build_intermediate_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)


def _baseline_ws2_cases() -> list[tuple[str, str, int]]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        (
            item["relative_path"],
            Path(item["relative_path"]).stem,
            item["expected_article_count"],
        )
        for item in baseline
        if item["expected_extraction_class"] == ExtractionClass.W.value
        and item["expected_content_class"] == ContentClass.S2.value
    ]


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count"),
    _baseline_ws2_cases(),
)
def test_real_ws2_boundary_confirms_clean_body_with_evidence(
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
    data_before = tuple(
        sorted(path.relative_to(data_root).as_posix() for path in data_root.rglob("*"))
    ) if data_root.exists() else ()

    record = classify_source(source)
    extraction = WordLegalExtractor().extract(
        ExtractionRequest.from_source_record(record, run_id="real-s2-boundary")
    )

    intermediate = S2BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )

    article_units = [
        unit for unit in intermediate.body_units if unit.kind == "article"
    ]

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.content_class is ContentClass.S2
    assert intermediate.schema_version == "legal-intermediate-v2"
    assert intermediate.body_text.startswith(expected_title)
    assert len(article_units) == expected_article_count
    assert article_units[0].text.startswith("第一条")
    assert article_units[-1].text.startswith(f"第{_int_to_chinese(expected_article_count)}条")
    assert "PAGE \\* MERGEFORMAT" not in intermediate.body_text
    assert before_digest == sha256(source.source_path.read_bytes()).hexdigest()
    assert data_before == tuple(
        sorted(path.relative_to(data_root).as_posix() for path in data_root.rglob("*"))
    ) if data_root.exists() else ()


def test_real_ws2_hebei_file_excludes_attachment2_and_revision_material():
    relative_path = "事故调查、问责与系统治理/河北省消防设施管理规定.docx"
    expected_title = "河北省消防设施管理规定"
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    record = classify_source(source)
    extraction = WordLegalExtractor().extract(
        ExtractionRequest.from_source_record(record, run_id="real-s2-hebei")
    )

    intermediate = S2BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )

    assert intermediate.boundary.status == "confirmed"
    assert "附件2" not in intermediate.body_text
    assert "河北省人民政府令" not in intermediate.body_text
    assert "省长" not in intermediate.body_text
    assert "将《河北省消防设施管理规定》第三条" not in intermediate.body_text
    leading_excluded = [
        excluded
        for excluded in intermediate.extraction_report.excluded_ranges
        if excluded.kind == "leading_publication_material"
    ]
    assert len(leading_excluded) == 1
    assert "publication_and_revision_material_before_target_title" in leading_excluded[0].reason


def test_real_ws2_social_fire_file_selects_second_title_and_has_authority_date_evidence():
    relative_path = "事故调查、问责与系统治理/社会消防安全教育培训规定.doc"
    expected_title = "社会消防安全教育培训规定"
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    record = classify_source(source)
    extraction = WordLegalExtractor().extract(
        ExtractionRequest.from_source_record(record, run_id="real-s2-social")
    )

    intermediate = S2BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )

    assert intermediate.boundary.status == "confirmed"
    title_block_orders = [
        block.order
        for block in extraction.text_blocks
        if block.text.strip() == expected_title
    ]
    selected_title_order = intermediate.body_units[0].source_span.start.block_order
    assert selected_title_order == max(title_block_orders)
    assert "公安部部长" not in intermediate.body_text
    assert "（第109号）" not in intermediate.body_text
    assert "二○○九年四月十三日" not in intermediate.body_text

    evidence_fields = {ev.field_name: ev for ev in intermediate.target.evidence}
    assert "issuing_authority" in evidence_fields
    assert evidence_fields["issuing_authority"].extraction_status == "confirmed"
    assert "公安部" in evidence_fields["issuing_authority"].value
    assert "promulgated_on" in evidence_fields
    assert evidence_fields["promulgated_on"].extraction_status == "confirmed"
    assert "年" in evidence_fields["promulgated_on"].value


_EXCLUDED_LEADING_SUBSTRINGS = {
    "河北省消防设施管理规定.docx": (
        "河北省人民政府令",
        "省长",
        "附件2",
        "将《河北省消防设施管理规定》第三条",
    ),
    "社会消防安全教育培训规定.doc": (
        "公安部部长",
        "（第109号）",
        "二○○九年四月十三日",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count"),
    _baseline_ws2_cases(),
)
def test_real_ws2_pipeline_structured_and_chunks_are_clean(
    relative_path,
    expected_title,
    expected_article_count,
    tmp_path,
):
    file_name = Path(relative_path).name
    excluded = _EXCLUDED_LEADING_SUBSTRINGS.get(file_name, ())
    batch = freeze_batch_input(TODO_ROOT)
    source = next(
        item for item in batch.sources if item.relative_path == relative_path
    )
    orchestrator = LegalIngestionOrchestrator(
        classifier=classify_source,
        extraction_registry=build_extraction_strategy_registry(
            word_extractor=WordLegalExtractor()
        ),
        boundary_registry=build_boundary_strategy_registry(
            s1_strategy=S1BoundaryStrategy(),
            s2_strategy=S2BoundaryStrategy(),
        ),
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=source),
        run_id=f"real-s2-pipeline-{expected_title}",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    intermediate = outcome.boundary_result
    assert intermediate.content_class is ContentClass.S2
    assert intermediate.boundary.status == "confirmed"

    normalized_path = tmp_path / "normalized" / f"{intermediate.document_id}.txt"
    write_confirmed_normalized(intermediate, normalized_path.parent)
    normalized_text = normalized_path.read_text(encoding="utf-8")
    for substr in excluded:
        assert substr not in normalized_text

    parsed = parse_legal_intermediate(intermediate)
    assert parsed.title == expected_title
    assert parsed.content_class == ContentClass.S2.value
    assert len(parsed.articles) == expected_article_count
    assert parsed.metadata_evidence == intermediate.target.evidence
    assert any(
        ev.field_name == "issuing_authority"
        and ev.extraction_status == "confirmed"
        for ev in parsed.metadata_evidence
    )
    assert any(
        ev.field_name == "promulgated_on"
        and ev.extraction_status == "confirmed"
        for ev in parsed.metadata_evidence
    )

    chunks = build_intermediate_chunks(intermediate, parsed)
    assert chunks
    assert all(
        chunk["document_id"] == intermediate.document_id
        and chunk["content_class"] == ContentClass.S2.value
        and chunk["source_sha256"] == source.source_sha256
        and chunk["version_basis"] == parsed.version_basis
        and chunk["revision_events"] == parsed.revision_events
        for chunk in chunks
    )
    for chunk in chunks:
        for substr in excluded:
            assert substr not in chunk["text"]

def _int_to_chinese(n: int) -> str:
    digits = "零一二三四五六七八九十"
    if n <= 10:
        return digits[n]
    if n < 20:
        return "十" + (digits[n - 10] if n != 10 else "")
    tens, ones = divmod(n, 10)
    return digits[tens] + "十" + (digits[ones] if ones else "")
