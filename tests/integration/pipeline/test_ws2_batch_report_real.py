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


def test_real_ws2_dry_run_report_matches_expectations(tmp_path, monkeypatch, capsys):
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

    batch_report_key = "batch_report="
    assert batch_report_key in captured.out
    batch_report_path = Path(
        captured.out.split(batch_report_key, 1)[1].split("\n", 1)[0].strip()
    )
    assert batch_report_path.exists()

    batch_report = json.loads(batch_report_path.read_text(encoding="utf-8"))
    assert batch_report["summary"]["auto_passed"] == 2
    assert batch_report["summary"]["committed"] == 0
    assert batch_report["summary"]["failed"] == 0
    assert batch_report["summary"]["review_required"] == 0
    assert len(batch_report["results"]) == 2

    expected_files = {
        "河北省消防设施管理规定.docx",
        "社会消防安全教育培训规定.doc",
    }
    found_files = {Path(item["relative_path"]).name for item in batch_report["results"]}
    assert found_files == expected_files

    for item in batch_report["results"]:
        assert item["source_sha256"]
        assert item["document_id"].startswith("doc_")
        assert item["quality_report_path"]
        assert Path(item["quality_report_path"]).exists()
        assert item["quality_report_sha256"]

        quality = json.loads(
            Path(item["quality_report_path"]).read_text(encoding="utf-8")
        )
        assert quality["ruleset_version"] == "legal-quality-v3"
        assert quality["overall"] == "pass"

        gate_ids = {gate["gate_id"] for gate in quality["gates"]}
        assert "s2_leading_material_isolation" in gate_ids
        assert "s2_metadata_traceability" in gate_ids
        for gate in quality["gates"]:
            assert gate["outcome"] == "pass"

    assert not (data_dir / "normalized").exists() or not any(
        (data_dir / "normalized").iterdir()
    )
    assert not (data_dir / "structured").exists() or not any(
        (data_dir / "structured").iterdir()
    )
    assert not (data_dir / "chunks").exists() or not any(
        (data_dir / "chunks").iterdir()
    )
    assert not (data_dir / "manifests" / "incremental_imports.json").exists()
