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


def _digest_sources(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}


def test_real_word_sources_match_expected_independent_classification_axes():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    expected_word = {
        item["relative_path"]: item
        for item in baseline
        if item["declared_extension"] in {".doc", ".docx"}
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
        content_class=ContentClass.S1,
    )

    assert len(records) == 11
    assert all(record.extraction_class is ExtractionClass.W for record in records)
    assert all(
        record.classification.disposition is ClassificationDisposition.READY
        for record in records
    )
    assert {
        record.source.relative_path: record.content_class.value
        for record in records
    } == {
        relative_path: item["expected_content_class"]
        for relative_path, item in expected_word.items()
    }
    assert [record.source.relative_path for record in selected] == sorted(
        relative_path
        for relative_path, item in expected_word.items()
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S1"
    )
    assert len(selected) == 8
    assert before == _digest_sources(source_paths)
