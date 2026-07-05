from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

import scripts.eval_ws_rag.dashboard_loader as dashboard_loader


_DEFAULT_REPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "reports" / "ws_rag_eval"
_VIEWS = ["总览", "文件列表", "问题下钻", "对比状态"]


def _report_root() -> Path:
    env_value = os.environ.get("EVAL_DASHBOARD_REPORT_ROOT")
    return Path(env_value) if env_value else _DEFAULT_REPORT_ROOT


def _init_session_state() -> None:
    if "dashboard_snapshot" not in st.session_state:
        st.session_state.dashboard_snapshot = dashboard_loader.build_snapshot(_report_root())
    if "selected_view" not in st.session_state:
        st.session_state.selected_view = "总览"
    if "selected_document_id" not in st.session_state:
        st.session_state.selected_document_id = None
    if "selected_question_id" not in st.session_state:
        st.session_state.selected_question_id = None
    if "dashboard_load_error" not in st.session_state:
        st.session_state.dashboard_load_error = None


def _on_refresh() -> None:
    try:
        current_id: str | None = None
        snapshot = st.session_state.get("dashboard_snapshot")
        if snapshot is not None and snapshot.current_run is not None:
            current_id = snapshot.current_run.run_id
        with st.spinner("刷新中…"):
            st.session_state.dashboard_snapshot = dashboard_loader.build_snapshot(
                _report_root(), current_id
            )
        st.session_state.dashboard_load_error = None
    except Exception as exc:  # noqa: BLE001
        st.session_state.dashboard_load_error = str(exc)


def _switch_run(snapshot: dashboard_loader.DashboardSnapshot, run_id: str) -> dashboard_loader.DashboardSnapshot:
    """Return a new snapshot that keeps the catalog but selects ``run_id``."""
    new_current = None
    for run in snapshot.catalog.valid_runs:
        if run.run_id == run_id:
            new_current = run
            break
    if new_current is None and snapshot.catalog.valid_runs:
        new_current = snapshot.catalog.valid_runs[0]
    return dashboard_loader.DashboardSnapshot(
        root_dir=snapshot.root_dir,
        catalog=snapshot.catalog,
        current_run=new_current,
        single_run_view=(
            dashboard_loader.build_single_run_view(new_current) if new_current else None
        ),
        loaded_at=dashboard_loader.utc_now(),
    )


def _render_sidebar(snapshot: dashboard_loader.DashboardSnapshot) -> str:
    st.sidebar.title("本机评测调试工具")

    run_options = [run.run_id for run in snapshot.catalog.valid_runs]
    current_index = 0
    if snapshot.current_run is not None and snapshot.current_run.run_id in run_options:
        current_index = run_options.index(snapshot.current_run.run_id)

    if run_options:
        selected_run_id = st.sidebar.selectbox(
            "当前 Run",
            options=run_options,
            index=current_index,
            key="run_selector",
        )
        if selected_run_id != snapshot.current_run.run_id if snapshot.current_run else True:
            snapshot = _switch_run(snapshot, selected_run_id)
            st.session_state.dashboard_snapshot = snapshot
    else:
        st.sidebar.selectbox("当前 Run", options=["无可用报告"], index=0, disabled=True)

    selected_view = st.sidebar.radio(
        "视图",
        options=_VIEWS,
        index=_VIEWS.index(st.session_state.selected_view),
    )
    st.session_state.selected_view = selected_view

    st.sidebar.button("刷新报告", key="refresh_button", on_click=_on_refresh)

    if snapshot.current_run is not None:
        run = snapshot.current_run
        st.sidebar.divider()
        st.sidebar.subheader("Run 元信息")
        st.sidebar.text(f"created_at: {run.created_at.isoformat()}")
        st.sidebar.text(f"dataset: {run.report.dataset.dataset_id}")
        st.sidebar.text(f"生成模型: {run.report.protocol.answer_model}")
        st.sidebar.text(f"Judge 模型: {run.report.protocol.judge_model}")
        st.sidebar.text(f"代码 commit: {run.report.system.git_commit}")

    return selected_view


def _render_header(snapshot: dashboard_loader.DashboardSnapshot, view: str) -> None:
    run_label = snapshot.current_run.run_id if snapshot.current_run else "无可用报告"
    st.header(f"{view} · {run_label}")


def _render_empty_state() -> None:
    st.info("你还没有任何评测结果，先去评测一下吧")


def _render_overview(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    st.write("总览视图")


def _render_file_list(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    st.write("文件列表视图")


def _render_drilldown(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    st.write("问题下钻视图")


def _render_comparison(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    st.write("对比状态视图")


def main() -> None:
    st.set_page_config(page_title="消防 RAG 评测 Dashboard", layout="wide")
    _init_session_state()

    snapshot: dashboard_loader.DashboardSnapshot = st.session_state.dashboard_snapshot
    selected_view = _render_sidebar(snapshot)
    snapshot = st.session_state.dashboard_snapshot

    _render_header(snapshot, selected_view)

    if st.session_state.dashboard_load_error is not None:
        st.error(f"刷新失败：{st.session_state.dashboard_load_error}")

    if not snapshot.catalog.valid_runs:
        _render_empty_state()
        return

    if selected_view == "总览":
        _render_overview(snapshot)
    elif selected_view == "文件列表":
        _render_file_list(snapshot)
    elif selected_view == "问题下钻":
        _render_drilldown(snapshot)
    elif selected_view == "对比状态":
        _render_comparison(snapshot)


if __name__ == "__main__":
    main()
