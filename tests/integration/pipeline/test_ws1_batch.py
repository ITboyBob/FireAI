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


def test_batch_verify_source_only_counts_eight_ws1_files(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
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
    assert "discovered=8" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())


def test_batch_dry_run_does_not_publish_formal_artifacts(tmp_path, monkeypatch, capsys):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "selected=8" in captured.out
    assert "batch_report=" in captured.out
    assert not (data_dir / "normalized").exists() or not any((data_dir / "normalized").iterdir())
    assert not (data_dir / "structured").exists() or not any((data_dir / "structured").iterdir())
    assert not (data_dir / "chunks").exists() or not any((data_dir / "chunks").iterdir())
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()


def test_batch_dry_run_writes_quality_reports(tmp_path, monkeypatch):
    result, data_dir = _run_cli(
        [
            "--batch-manifest",
            str(FIXTURE_MANIFEST),
            "--source-root",
            str(SOURCE_ROOT),
            "--dry-run",
        ],
        monkeypatch,
        tmp_path,
    )

    batch_dir = next((data_dir / "manifests" / "legal_ingestion_batches").iterdir())
    quality_reports = list(batch_dir.glob("*.quality.json"))
    assert len(quality_reports) == 8
    for report_path in quality_reports:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert "ruleset_version" in payload
        assert "overall" in payload
        assert "gates" in payload


def test_batch_manifest_requires_existing_source_files(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "relative_path": "missing/不存在的文件.doc",
                    "expected_extraction_class": "W",
                    "expected_content_class": "S1",
                }
            ]
        ),
        encoding="utf-8",
    )

    result, _ = _run_cli(
        ["--batch-manifest", str(manifest_path)],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "源文件缺失" in captured.err


def test_batch_manifest_is_mutually_exclusive_with_single_source(tmp_path, monkeypatch, capsys):
    source = tmp_path / "单个文件.docx"
    source.write_text("placeholder", encoding="utf-8")

    result, _ = _run_cli(
        ["--batch-manifest", str(FIXTURE_MANIFEST), "--source", str(source)],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "互斥" in captured.err


def test_dry_run_requires_batch_manifest(tmp_path, monkeypatch, capsys):
    source = tmp_path / "单个文件.docx"
    source.write_text("placeholder", encoding="utf-8")

    result, _ = _run_cli(
        ["--source", str(source), "--dry-run"],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "--dry-run" in captured.err


def test_verify_source_only_requires_batch_manifest(tmp_path, monkeypatch, capsys):
    source = tmp_path / "单个文件.docx"
    source.write_text("placeholder", encoding="utf-8")

    result, _ = _run_cli(
        ["--source", str(source), "--verify-source-only"],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "--verify-source-only" in captured.err


def test_batch_manifest_rejects_path_traversal(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "relative_path": "../outside/traversal.doc",
                    "expected_extraction_class": "W",
                    "expected_content_class": "S1",
                }
            ]
        ),
        encoding="utf-8",
    )

    result, _ = _run_cli(
        ["--batch-manifest", str(manifest_path)],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "不允许跳出 source_root" in captured.err


def test_batch_manifest_rejects_absolute_relative_path(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "relative_path": "/absolute/path.doc",
                    "expected_extraction_class": "W",
                    "expected_content_class": "S1",
                }
            ]
        ),
        encoding="utf-8",
    )

    result, _ = _run_cli(
        ["--batch-manifest", str(manifest_path)],
        monkeypatch,
        tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "必须是相对路径" in captured.err
