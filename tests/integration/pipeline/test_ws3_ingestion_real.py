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
from app.services.legal_s3_boundary import S3BoundaryStrategy
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


def _baseline_ws3_cases() -> list[tuple[str, str, int]]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        (
            item["relative_path"],
            Path(item["relative_path"]).stem,
            item["expected_article_count"],
        )
        for item in baseline
        if item["expected_extraction_class"] == ExtractionClass.W.value
        and item["expected_content_class"] == ContentClass.S3.value
    ]


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count"),
    _baseline_ws3_cases(),
)
def test_real_ws3_boundary_confirms_clean_body_with_excluded_ranges(
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
        ExtractionRequest.from_source_record(record, run_id="real-s3-boundary")
    )

    intermediate = S3BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title=expected_title,
    )

    article_units = [
        unit for unit in intermediate.body_units if unit.kind == "article"
    ]

    assert intermediate.boundary.status == "confirmed"
    assert intermediate.content_class is ContentClass.S3
    assert intermediate.schema_version == "legal-intermediate-v2"
    assert intermediate.body_text.startswith(expected_title)
    assert len(article_units) == expected_article_count
    assert article_units[0].text.startswith("第一条")
    assert article_units[-1].text.startswith(f"第{_int_to_chinese(expected_article_count)}条")
    assert "PAGE \\ * MERGEFORMAT" not in intermediate.body_text
    assert "行政执法监督文书" not in intermediate.body_text
    assert "姓名：" not in intermediate.body_text
    assert "单位：" not in intermediate.body_text
    excluded = intermediate.extraction_report.excluded_ranges
    assert excluded
    kinds = {er.kind for er in excluded}
    assert "attachment_index" in kinds
    assert "form_template" in kinds
    assert "trailing_print_metadata" in kinds
    assert before_digest == sha256(source.source_path.read_bytes()).hexdigest()
    assert data_before == tuple(
        sorted(path.relative_to(data_root).as_posix() for path in data_root.rglob("*"))
    ) if data_root.exists() else ()


@pytest.mark.parametrize(
    ("relative_path", "expected_title", "expected_article_count"),
    _baseline_ws3_cases(),
)
def test_real_ws3_pipeline_structured_and_chunks_are_clean(
    relative_path,
    expected_title,
    expected_article_count,
    tmp_path,
):
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
            s3_strategy=S3BoundaryStrategy(),
        ),
    )

    outcome = orchestrator.prepare(
        IngestionInput(single_source=source),
        run_id=f"real-s3-pipeline-{expected_title}",
    )[0]

    assert outcome.disposition is IngestionDisposition.READY
    intermediate = outcome.boundary_result
    assert intermediate.content_class is ContentClass.S3
    assert intermediate.boundary.status == "confirmed"

    normalized_path = tmp_path / "normalized" / f"{intermediate.document_id}.txt"
    write_confirmed_normalized(intermediate, normalized_path.parent)
    normalized_text = normalized_path.read_text(encoding="utf-8")
    assert "行政执法监督文书" not in normalized_text
    assert "姓名：" not in normalized_text
    assert "单位：" not in normalized_text
    assert "PAGE" not in normalized_text

    parsed = parse_legal_intermediate(intermediate)
    assert parsed.title == expected_title
    assert parsed.content_class == ContentClass.S3.value
    assert len(parsed.articles) == expected_article_count

    chunks = build_intermediate_chunks(intermediate, parsed)
    assert chunks
    assert all(
        chunk["document_id"] == intermediate.document_id
        and chunk["content_class"] == ContentClass.S3.value
        and chunk["source_sha256"] == source.source_sha256
        and chunk["boundary_status"] == "confirmed"
        for chunk in chunks
    )
    for chunk in chunks:
        assert "行政执法监督文书" not in chunk["text"]
        assert "姓名：" not in chunk["text"]
        assert "单位：" not in chunk["text"]
        assert "PAGE" not in chunk["text"]


def _int_to_chinese(n: int) -> str:
    digits = "零一二三四五六七八九十"
    if n <= 10:
        return digits[n]
    if n < 20:
        return "十" + (digits[n - 10] if n != 10 else "")
    tens, ones = divmod(n, 10)
    return digits[tens] + "十" + (digits[ones] if ones else "")
