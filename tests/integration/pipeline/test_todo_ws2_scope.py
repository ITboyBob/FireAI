from hashlib import sha256
import json
from pathlib import Path

from app.services.legal_ingestion_inventory import freeze_batch_input, select_scope
from app.services.legal_ingestion_models import (
    ClassificationDisposition,
    ContentClass,
    ExtractionClass,
)
from app.services.legal_source_classifier import classify_source


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)


WS2_PATHS = (
    "事故调查、问责与系统治理/河北省消防设施管理规定.docx",
    "事故调查、问责与系统治理/社会消防安全教育培训规定.doc",
)


def _digest_sources(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}


def test_ws2_scope_is_derived_from_unique_baseline():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    expected_ws2 = {
        item["relative_path"]: item
        for item in baseline
        if item["expected_extraction_class"] == ExtractionClass.W.value
        and item["expected_content_class"] == ContentClass.S2.value
    }

    batch = freeze_batch_input(TODO_ROOT)
    word_sources = tuple(
        source
        for source in batch.sources
        if source.declared_extension in {".doc", ".docx"}
    )
    source_paths = tuple(source.source_path for source in word_sources)
    before = _digest_sources(source_paths)

    records = tuple(classify_source(source) for source in word_sources)
    selected = select_scope(
        records,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S2,
    )

    assert sorted(expected_ws2.keys()) == sorted(WS2_PATHS)
    assert len(selected) == 2
    assert {record.source.relative_path for record in selected} == set(WS2_PATHS)
    assert all(record.extraction_class is ExtractionClass.W for record in selected)
    assert all(record.content_class is ContentClass.S2 for record in selected)
    assert all(
        record.classification.disposition is ClassificationDisposition.READY
        for record in selected
    )
    for record in selected:
        expected = expected_ws2[record.source.relative_path]
        assert expected["expected_article_count"] is not None
    assert before == _digest_sources(source_paths)


def test_no_ws2_candidate_helper_or_second_baseline_created(tmp_path):
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    ws2_records = [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S2"
    ]
    assert len(ws2_records) == 2
    assert not (tmp_path / "ws2_baseline.json").exists()
