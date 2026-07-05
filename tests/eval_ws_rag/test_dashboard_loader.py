import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.eval_ws_rag.report_models import EvaluationReport


class TestSharedSchema:
    def test_dashboard_loader_reuses_shared_report_models(self):
        from scripts.eval_ws_rag import report_models

        assert "schema_version" in report_models.EvaluationReport.model_fields


FIXTURES_DIR = Path(__file__).with_name("fixtures")
REPORT_FIXTURE = FIXTURES_DIR / "valid_report.json"
ERRORS_FIXTURE = FIXTURES_DIR / "valid_errors.json"


def _load_report_dict(path: Path = REPORT_FIXTURE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_errors_dict(path: Path = ERRORS_FIXTURE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_run(
    root: Path,
    run_id: str,
    report_data: dict | None = None,
    errors_data: dict | None = None,
) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    report = (report_data or _load_report_dict()).copy()
    report["run_id"] = run_id
    report["created_at"] = "2026-07-05T00:00:00+00:00"
    errors = (errors_data or _load_errors_dict()).copy()
    errors["run_id"] = run_id
    errors["created_at"] = report["created_at"]
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (run_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False), encoding="utf-8")
    return run_dir


class TestDiscoverRuns:
    def test_discover_runs_loads_the_single_valid_mock_run(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_20260705_000000_mock001"
        _write_run(tmp_path, run_id)

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 1
        assert catalog.valid_runs[0].run_id == run_id
        assert len(catalog.invalid_runs) == 0

    def test_discover_runs_ignores_staging_hidden_and_symlink(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        valid_id = "run_valid_001"
        _write_run(tmp_path, valid_id)

        # Staging directory
        staging = tmp_path / ".run_staging_001.tmp"
        staging.mkdir()
        (staging / "report.json").write_text("{}", encoding="utf-8")

        # Hidden directory
        hidden = tmp_path / ".hidden_run"
        hidden.mkdir()
        (hidden / "report.json").write_text("{}", encoding="utf-8")

        # Symlink to valid run
        symlink = tmp_path / "symlink_run"
        symlink.symlink_to(tmp_path / valid_id)

        # Missing errors.json
        missing = tmp_path / "run_missing_errors"
        missing.mkdir()
        (missing / "report.json").write_text("{}", encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 1
        assert catalog.valid_runs[0].run_id == valid_id
        assert len(catalog.invalid_runs) == 1
        assert catalog.invalid_runs[0].category == "missing_file"

    def test_discover_runs_rejects_directory_run_id_mismatch(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_dir = tmp_path / "run_dir_name"
        run_dir.mkdir()
        report = _load_report_dict()
        report["run_id"] = "run_inside_json"
        errors = _load_errors_dict()
        errors["run_id"] = "run_inside_json"
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        (run_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "cross_file_inconsistent" and "run_id" in invalid.reason
            for invalid in catalog.invalid_runs
        )

    def test_discover_runs_empty_root_returns_empty_catalog(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        catalog = discover_runs(tmp_path)
        assert catalog.valid_runs == []
        assert catalog.invalid_runs == []

    def test_discover_runs_missing_root_returns_empty_catalog(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        catalog = discover_runs(tmp_path / "does_not_exist")
        assert catalog.valid_runs == []
        assert catalog.invalid_runs == []

    def test_discover_runs_unknown_major_is_invalid(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_bad_version"
        run_dir = _write_run(tmp_path, run_id)
        report = _load_report_dict()
        report["schema_version"] = "2.0.0"
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "unsupported_schema" for invalid in catalog.invalid_runs
        )

    def test_discover_runs_missing_errors_is_invalid(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_dir = tmp_path / "run_no_errors"
        run_dir.mkdir()
        report = _load_report_dict()
        report["run_id"] = "run_no_errors"
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "missing_file" for invalid in catalog.invalid_runs
        )

    def test_discover_runs_cross_file_inconsistent_created_at(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_mismatch_time"
        run_dir = _write_run(tmp_path, run_id)
        errors = _load_errors_dict()
        errors["run_id"] = run_id
        errors["created_at"] = "2026-07-06T00:00:00+00:00"
        (run_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "cross_file_inconsistent" and "created_at" in invalid.reason
            for invalid in catalog.invalid_runs
        )

    def test_discover_runs_cross_field_inconsistent_question_count(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_bad_counts"
        run_dir = _write_run(tmp_path, run_id)
        report = _load_report_dict()
        report["run_id"] = run_id
        report["created_at"] = "2026-07-05T00:00:00+00:00"
        report["summary"]["question_count"] = 999
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        # The shared schema validator catches this as a validation error.
        assert len(catalog.invalid_runs) == 1

    def test_discover_runs_citation_bound_to_missing_chunk_is_invalid(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_bad_citation"
        run_dir = _write_run(tmp_path, run_id)
        report = _load_report_dict()
        report["run_id"] = run_id
        report["created_at"] = "2026-07-05T00:00:00+00:00"
        report["documents"][0]["questions"][0]["citations"][0]["matched_chunk_id"] = "no_such_chunk"
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "cross_field_inconsistent" and "matched_chunk_id" in invalid.reason
            for invalid in catalog.invalid_runs
        )

    def test_discover_runs_question_id_duplicated_is_invalid(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        run_id = "run_dup_qid"
        run_dir = _write_run(tmp_path, run_id)
        report = _load_report_dict()
        report["run_id"] = run_id
        report["created_at"] = "2026-07-05T00:00:00+00:00"
        q = report["documents"][0]["questions"][0]
        report["documents"][0]["questions"].append(q)
        report["documents"][0]["question_count"] = len(report["documents"][0]["questions"])
        report["documents"][0]["passed_questions"] = 3
        report["summary"]["question_count"] = 4
        report["summary"]["passed_questions"] = 3
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        catalog = discover_runs(tmp_path)
        assert len(catalog.valid_runs) == 0
        assert any(
            invalid.category == "cross_field_inconsistent" and "重复" in invalid.reason
            for invalid in catalog.invalid_runs
        )


class TestSnapshot:
    def test_build_snapshot_keeps_current_run_selection(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        older = "run_older"
        newer = "run_newer"
        _write_run(tmp_path, older)
        _write_run(tmp_path, newer)

        snapshot = build_snapshot(tmp_path, current_run_id=older)
        assert snapshot.current_run is not None
        assert snapshot.current_run.run_id == older
        assert len(snapshot.catalog.valid_runs) == 2

    def test_build_snapshot_becomes_empty_when_the_only_run_disappears(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        snapshot = build_snapshot(tmp_path, current_run_id="ghost_run")
        assert snapshot.current_run is None
        assert snapshot.single_run_view is None
        assert snapshot.catalog.valid_runs == []

    def test_build_snapshot_falls_back_to_latest_when_current_removed(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        only_id = "run_only"
        _write_run(tmp_path, only_id)

        snapshot = build_snapshot(tmp_path, current_run_id="ghost_run")
        assert snapshot.current_run is not None
        assert snapshot.current_run.run_id == only_id


class TestSingleRunView:
    def test_single_run_derives_failure_and_error_counts(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        run_id = "run_counts"
        _write_run(tmp_path, run_id)

        snapshot = build_snapshot(tmp_path)
        view = snapshot.single_run_view
        assert view is not None
        assert view.failure_code_counts.get("citation_invalid") == 1
        assert view.failure_code_counts.get("refusal_missed") == 1
        assert view.error_stage_counts.get("rule_validation") == 1

    def test_single_run_comparison_state_is_unavailable(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        _write_run(tmp_path, "run_one")
        snapshot = build_snapshot(tmp_path)
        view = snapshot.single_run_view
        assert view is not None
        assert view.comparison_available is False
        assert "只有一个 Run" in view.comparison_message

    def test_single_run_never_exposes_directional_deltas(self, tmp_path):
        from scripts.eval_ws_rag.dashboard_loader import build_snapshot

        _write_run(tmp_path, "run_one")
        snapshot = build_snapshot(tmp_path)
        view = snapshot.single_run_view
        assert view is not None
        assert not hasattr(view, "delta")
        assert not hasattr(view, "improved")
        assert not hasattr(view, "regressed")


class TestRealFixture:
    def test_valid_fixture_is_accepted_by_loader(self):
        from scripts.eval_ws_rag.dashboard_loader import discover_runs

        root = Path("/tmp") / "fire_fixture_validation"
        root.mkdir(parents=True, exist_ok=True)
        run_id = "run_20260705_000000_mock001"
        run_dir = root / run_id
        if run_dir.exists():
            import shutil

            shutil.rmtree(run_dir)
        run_dir.mkdir()
        (run_dir / "report.json").write_bytes(REPORT_FIXTURE.read_bytes())
        (run_dir / "errors.json").write_bytes(ERRORS_FIXTURE.read_bytes())

        catalog = discover_runs(root)
        assert len(catalog.valid_runs) == 1
        assert catalog.valid_runs[0].run_id == run_id
        assert len(catalog.invalid_runs) == 0

        import shutil

        shutil.rmtree(root)
