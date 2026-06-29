from hashlib import sha256
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)


def _source_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _discover_relative_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(TODO_ROOT).as_posix()
            for path in TODO_ROOT.rglob("*")
            if path.is_file() and path.name != ".DS_Store"
        )
    )


def test_todo_baseline_matches_real_sources_and_derives_ws1_scope():
    before = {
        relative_path: _source_digest(TODO_ROOT / relative_path)
        for relative_path in _discover_relative_paths()
    }
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    baseline_paths = [item["relative_path"] for item in baseline]
    ws1 = [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S1"
    ]

    assert len(baseline) == 14
    assert len(baseline_paths) == len(set(baseline_paths))
    assert tuple(sorted(baseline_paths)) == _discover_relative_paths()
    assert len(ws1) == 8
    assert all(item["declared_extension"] in {".doc", ".docx", ".pdf"} for item in baseline)
    assert all(
        set(item)
        == {
            "relative_path",
            "declared_extension",
            "expected_extraction_class",
            "expected_content_class",
            "expected_article_count",
            "risk_codes",
        }
        for item in baseline
    )
    assert before == {
        relative_path: _source_digest(TODO_ROOT / relative_path)
        for relative_path in _discover_relative_paths()
    }
