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
EXPECTED_WS3_RELATIVE_PATH = "督察、处罚与监管/河北省消防救援机构执法过错责任追究规定.doc"


def _digest_sources(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}


def test_todo_baseline_has_exactly_one_ws3_item():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    ws3_items = [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S3"
    ]

    assert len(ws3_items) == 1
    item = ws3_items[0]
    assert item["relative_path"] == EXPECTED_WS3_RELATIVE_PATH
    assert item["expected_article_count"] == 29
    assert "tail_template" in item["risk_codes"]
    assert "word_page_field" in item["risk_codes"]


def test_ws3_source_file_exists_and_is_read_only():
    source_path = TODO_ROOT / EXPECTED_WS3_RELATIVE_PATH
    assert source_path.exists(), f"W-S3 真实源文件缺失: {source_path}"
    assert source_path.is_file()
    before = sha256(source_path.read_bytes()).hexdigest()
    after = sha256(source_path.read_bytes()).hexdigest()
    assert before == after, "W-S3 源文件在只读探测期间发生变化"


def test_real_ws3_source_classifies_as_w_s3():
    batch = freeze_batch_input(TODO_ROOT)
    ws3_sources = tuple(
        source
        for source in batch.sources
        if source.relative_path == EXPECTED_WS3_RELATIVE_PATH
    )
    assert len(ws3_sources) == 1
    source = ws3_sources[0]

    before = sha256(source.source_path.read_bytes()).hexdigest()
    record = classify_source(source)
    after = sha256(source.source_path.read_bytes()).hexdigest()

    assert before == after, "分类过程修改了 W-S3 源文件"
    assert record.extraction_class is ExtractionClass.W
    assert record.content_class is ContentClass.S3
    assert record.classification.disposition is ClassificationDisposition.READY

    records = tuple(classify_source(source) for source in batch.sources)
    selected = select_scope(
        records,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S3,
    )
    assert [record.source.relative_path for record in selected] == [
        EXPECTED_WS3_RELATIVE_PATH
    ]


def test_no_second_ws3_baseline_file():
    candidates = tuple(
        PROJECT_ROOT.rglob("*ws3*")
    )
    assert not any("baseline" in path.name.lower() for path in candidates), (
        "发现第二份 W-S3 基线文件，清单必须唯一"
    )
