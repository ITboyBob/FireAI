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


def test_batch_ws3_verify_source_only_counts_one_file(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S3",
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=1" in captured.out
    assert "discovered=1" in captured.out
    assert "failed=0" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())


def test_batch_ws3_dry_run_auto_passes_one_file(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "W",
            "--content-class",
            "S3",
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=1" in captured.out
    assert "auto_passed=1" in captured.out
    assert "committed=0" in captured.out
    assert "review_required=0" in captured.out
    assert "failed=0" in captured.out
    assert "unsupported=0" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()


def test_batch_default_without_class_filter_still_selects_ws1(
    tmp_path, monkeypatch, capsys
):
    result, _ = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=8" in captured.out


def test_batch_ps_s3_dry_run_is_review_required_without_writes(
    tmp_path, monkeypatch, capsys
):
    """PS 文件在分类阶段即因 unresolved_real_format 进入 review_required，不会提交。"""
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--extraction-class",
            "PS",
            "--content-class",
            "S3",
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


def test_batch_ws3_empty_selection_returns_zero_report(tmp_path, monkeypatch, capsys):
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
            "S3",
            "--verify-source-only",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "selected=0" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())
