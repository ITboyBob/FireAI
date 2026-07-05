import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.eval_ws_rag.dashboard_loader as dashboard_loader


FIXTURES_DIR = Path(__file__).with_name("fixtures")
REPORT_FIXTURE = FIXTURES_DIR / "valid_report.json"
ERRORS_FIXTURE = FIXTURES_DIR / "valid_errors.json"


def _load_report_dict() -> dict:
    return json.loads(REPORT_FIXTURE.read_text(encoding="utf-8"))


def _load_errors_dict() -> dict:
    return json.loads(ERRORS_FIXTURE.read_text(encoding="utf-8"))


def _write_run(root: Path, run_id: str) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    report = _load_report_dict().copy()
    report["run_id"] = run_id
    report["created_at"] = "2026-07-05T00:00:00+00:00"
    errors = _load_errors_dict().copy()
    errors["run_id"] = run_id
    errors["created_at"] = report["created_at"]
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (run_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False), encoding="utf-8")
    return run_dir


@pytest.fixture
def streamlit_app():
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "eval_ws_rag" / "dashboard.py"
    return AppTest.from_file(str(app_path), default_timeout=30)


class TestAppShellAndState:
    def test_app_loads_local_tool_shell(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        assert not at.exception
        titles = [t.value for t in at.sidebar.title]
        assert any("本机评测调试工具" in t for t in titles)

    def test_initial_load_builds_one_snapshot(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        assert not at.exception
        snapshot = at.session_state["dashboard_snapshot"]
        assert snapshot is not None
        assert snapshot.current_run is not None
        assert snapshot.current_run.run_id == "run_001"

    def test_view_change_does_not_rescan_disk(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        call_count = {"n": 0}
        original = dashboard_loader.build_snapshot

        def counted_build_snapshot(root_dir, current_run_id=None):
            call_count["n"] += 1
            return original(root_dir, current_run_id)

        with patch.object(dashboard_loader, "build_snapshot", counted_build_snapshot):
            at = streamlit_app.run()
            assert call_count["n"] == 1

            radio = at.sidebar.radio[0]
            radio.set_value("文件列表").run()
            assert call_count["n"] == 1
