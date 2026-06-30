from pathlib import Path
import json
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
SOURCE_ROOT = PROJECT_ROOT / "法律文本" / "todo"


def _run_cli(argv, monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INDEX_DIR", str(data_dir / "index"))
    return module["main"](argv), data_dir


def test_batch_ws2_verify_source_only_counts_two_files(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S2",
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=2" in captured.out
    assert "discovered=2" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())


def test_batch_ws2_dry_run_auto_passes_two_files(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S2",
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=2" in captured.out
    assert "auto_passed=2" in captured.out
    assert "committed=0" in captured.out
    assert "review_required=0" in captured.out
    assert "failed=0" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()


def test_batch_pt_s2_dry_run_is_rejected_without_writes(
    tmp_path, monkeypatch, capsys
):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "PT",
            "--content-class",
            "S2",
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 4
    assert "selected=1" in captured.out
    assert "review_required=1" in captured.out
    assert "committed=0" in captured.out
    assert "auto_passed=0" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()


def test_batch_ws2_explicit_is_equivalent_to_default_ws1_when_args_match(
    tmp_path, monkeypatch, capsys
):
    result, _ = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S1",
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=8" in captured.out


def test_batch_rejects_invalid_extraction_class(tmp_path, monkeypatch, capsys):
    result, _ = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "X",
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "invalid choice" in captured.err.lower()


def test_batch_rejects_invalid_content_class(tmp_path, monkeypatch, capsys):
    result, _ = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--content-class",
            "S5",
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "invalid choice" in captured.err.lower()


def test_single_source_with_class_filter_is_rejected(tmp_path, monkeypatch, capsys):
    source = tmp_path / "单个文件.docx"
    source.write_text("placeholder", encoding="utf-8")

    result, _ = _run_cli(
        [
            "--source",
            str(source),
            "--extraction-class",
            "W",
            "--content-class",
            "S2",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "互斥" in captured.err


def test_batch_empty_selection_returns_zero_report(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "relative_path": "某文件.doc",
                    "expected_extraction_class": "PT",
                    "expected_content_class": "S1",
                }
            ]
        ),
        encoding="utf-8",
    )

    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(manifest_path),
            "--extraction-class",
            "W",
            "--content-class",
            "S2",
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=0" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
