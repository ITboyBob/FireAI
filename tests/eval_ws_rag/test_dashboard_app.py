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



def _write_run_with_pass_rate(root: Path, run_id: str, overall_pass_rate: float) -> Path:
    run_dir = _write_run(root, run_id)
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report["summary"]["overall_pass_rate"] = overall_pass_rate
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return run_dir


class TestOverviewAndFileList:
    def test_overview_displays_report_values_without_regrading(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run_with_pass_rate(tmp_path, "run_042", 0.42)

        at = streamlit_app.run()
        assert not at.exception
        labels_values = {m.label: m.value for m in at.metric}
        assert labels_values.get("Overall Pass Rate") == "42%"
        assert labels_values.get("文件数") == "1"
        assert labels_values.get("问题数") == "3"
        assert labels_values.get("失败问题数") == "1"
        assert labels_values.get("红线失败数") == "1"

    def test_file_list_shows_text_status_and_metrics(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at.sidebar.radio[0].set_value("文件列表").run()
        assert not at.exception

        df = at.dataframe[0].value
        assert "消防监督检查规定" in df["标题"].values
        assert "红线失败" in df["状态"].values
        assert "context_relevancy" in df.columns
        assert "faithfulness" in df.columns

    def test_file_selectbox_is_available_as_selection_fallback(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at.sidebar.radio[0].set_value("文件列表").run()
        labels = [sb.label for sb in at.selectbox]
        assert "选择文件（兜底）" in labels

    def test_file_selection_updates_drilldown_state(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at.sidebar.radio[0].set_value("文件列表").run()

        file_selectbox = next(sb for sb in at.selectbox if sb.label == "选择文件（兜底）")
        at = file_selectbox.select("doc_d97773f1500c").run()
        assert not at.exception

        assert at.session_state["selected_view"] == "问题下钻"
        assert at.session_state["selected_document_id"] == "doc_d97773f1500c"



class TestDrilldown:
    def _enter_drilldown(self, at, document_id, question_id):
        at.session_state["selected_view"] = "问题下钻"
        at.session_state["selected_document_id"] = document_id
        at.session_state["selected_question_id"] = question_id
        return at.run()

    def test_drilldown_displays_scores_thresholds_and_failure_codes(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at = self._enter_drilldown(at, "doc_d97773f1500c", "q_boundary_001")
        assert not at.exception

        markdowns = " ".join(str(m.value) for m in at.markdown)
        assert "citation_invalid" in markdowns
        assert "refusal_missed" in markdowns
        assert "引文无法在当前证据中验证" in markdowns

        df = at.dataframe[0].value
        assert "上下文相关性" in df["指标"].values
        assert "阈值" in df.columns

    def test_drilldown_displays_retrieved_chunks_and_bound_citations(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at = self._enter_drilldown(at, "doc_d97773f1500c", "q_frequent_001")
        assert not at.exception

        captions = " ".join(str(c.value) for c in at.caption)
        assert "chunk_frequent_001" in captions
        assert "matched_chunk_id" in captions

    def test_red_line_help_is_only_shown_near_active_failure(self, streamlit_app, tmp_path, monkeypatch):
        monkeypatch.setenv("EVAL_DASHBOARD_REPORT_ROOT", str(tmp_path))
        _write_run(tmp_path, "run_001")

        at = streamlit_app.run()
        at = self._enter_drilldown(at, "doc_d97773f1500c", "q_boundary_001")
        assert any("红线失败" in str(e.value) for e in at.error)

        at = self._enter_drilldown(at, "doc_d97773f1500c", "q_frequent_001")
        assert not any("红线失败" in str(e.value) for e in at.error)
