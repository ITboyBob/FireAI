from hashlib import sha256
import json
from pathlib import Path

from app.services.legal_ingestion_inventory import freeze_batch_input


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


def _relative_tree(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
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


def test_real_todo_sources_freeze_to_the_same_fourteen_file_inventory():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    staging_root = PROJECT_ROOT / "data" / ".staging"
    staging_before = _relative_tree(staging_root)
    before = {
        relative_path: _source_digest(TODO_ROOT / relative_path)
        for relative_path in _discover_relative_paths()
    }

    batch = freeze_batch_input(TODO_ROOT)

    assert [source.relative_path for source in batch.sources] == sorted(
        item["relative_path"] for item in baseline
    )
    assert len(batch.sources) == 14
    assert len(batch.batch_digest) == 64
    assert before == {
        relative_path: _source_digest(TODO_ROOT / relative_path)
        for relative_path in _discover_relative_paths()
    }
    assert staging_before == _relative_tree(staging_root)
