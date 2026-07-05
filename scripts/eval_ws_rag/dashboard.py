from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
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
        current_run_id = snapshot.current_run.run_id if snapshot.current_run else None
        if selected_run_id != current_run_id:
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


def _document_status(document: dashboard_loader.DocumentScorecard) -> str:
    red = document.red_line_failures_count or 0
    failed = document.failed_questions_count or 0
    if red > 0:
        return "红线失败"
    if failed > 0:
        return "普通失败"
    return "通过"


def _select_document(doc_id: str) -> None:
    if st.session_state.get("selected_document_id") == doc_id:
        return
    st.session_state.selected_document_id = doc_id
    st.session_state.selected_question_id = None
    st.session_state.selected_view = "问题下钻"
    st.rerun()


def _on_file_selectbox_change() -> None:
    doc_id = st.session_state.get("file_selectbox")
    if doc_id:
        _select_document(doc_id)


def _render_empty_state() -> None:
    st.info("你还没有任何评测结果，先去评测一下吧")


def _render_overview(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    run = snapshot.current_run
    view = snapshot.single_run_view
    if run is None or view is None:
        st.info("暂无数据")
        return

    summary = run.report.summary
    protocol = run.report.protocol

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("文件数", len(run.report.documents))
    with col2:
        st.metric("问题数", summary.question_count)
    with col3:
        st.metric("Overall Pass Rate", f"{summary.overall_pass_rate:.0%}")
    with col4:
        st.metric("失败问题数", summary.failed_questions_count or 0)
    with col5:
        st.metric("红线失败数", summary.red_line_failures_count or 0)

    st.subheader("评测元信息")
    meta_df = pd.DataFrame(
        {
            "字段": [
                "dataset_id",
                "dataset_fingerprint",
                "protocol_fingerprint",
                "代码 commit",
                "生成模型",
                "Judge 模型",
                "top_k",
                "语料指纹",
            ],
            "值": [
                str(run.report.dataset.dataset_id),
                str(run.report.dataset.dataset_fingerprint),
                str(protocol.protocol_fingerprint),
                str(run.report.system.git_commit),
                str(protocol.answer_model),
                str(protocol.judge_model),
                str(protocol.top_k),
                str(run.report.system.corpus_fingerprint),
            ],
        }
    )
    st.dataframe(meta_df, use_container_width=True, hide_index=True)

    st.subheader("指标与阈值")
    metric_names = [
        "context_relevancy",
        "source_coverage",
        "faithfulness",
        "answer_relevance",
        "citation_validity",
        "refusal_appropriateness",
    ]
    metric_labels = [
        "上下文相关性",
        "来源覆盖",
        "忠实度",
        "回答相关性",
        "引文有效性",
        "拒答适当性",
    ]
    metrics_table = pd.DataFrame(
        {
            "指标": metric_labels,
            "得分": [getattr(summary.metrics, name) for name in metric_names],
            "阈值": [getattr(protocol.thresholds, name) for name in metric_names],
            "达标": [
                getattr(summary.metrics, name) >= getattr(protocol.thresholds, name)
                for name in metric_names
            ],
        }
    )
    st.dataframe(metrics_table, use_container_width=True, hide_index=True)

    st.subheader("文件状态分布")
    status_counts = {"通过": 0, "普通失败": 0, "红线失败": 0}
    for document in run.report.documents:
        status_counts[_document_status(document)] += 1
    status_df = pd.DataFrame(
        {"状态": list(status_counts.keys()), "文件数": list(status_counts.values())}
    )
    chart = (
        alt.Chart(status_df)
        .mark_bar()
        .encode(x=alt.X("状态", sort=None), y="文件数", color="状态")
        .properties(width="container")
    )
    st.altair_chart(chart)

    st.subheader("失败原因 Top")
    if view.failure_code_counts:
        failure_df = pd.DataFrame(
            {
                "失败代码": list(view.failure_code_counts.keys()),
                "次数": list(view.failure_code_counts.values()),
            }
        ).sort_values("次数", ascending=False)
        st.dataframe(failure_df, use_container_width=True, hide_index=True)
    else:
        st.caption("本轮没有失败原因")

    st.subheader("执行错误摘要")
    if view.error_stage_counts:
        error_df = pd.DataFrame(
            {
                "阶段": list(view.error_stage_counts.keys()),
                "次数": list(view.error_stage_counts.values()),
            }
        )
        st.dataframe(error_df, use_container_width=True, hide_index=True)
    else:
        st.caption("本轮没有执行错误")


def _render_file_list(snapshot: dashboard_loader.DashboardSnapshot) -> None:
    run = snapshot.current_run
    if run is None:
        st.info("暂无数据")
        return

    documents = run.report.documents
    if not documents:
        st.caption("没有文件数据")
        return

    show_only_failed = st.checkbox("只看失败文件", key="file_filter_failed")
    show_only_red = st.checkbox("只看红线文件", key="file_filter_red")

    rows = []
    for document in documents:
        failed = document.failed_questions_count or 0
        red = document.red_line_failures_count or 0
        if show_only_red and red == 0:
            continue
        if show_only_failed and failed == 0 and red == 0:
            continue
        rows.append(
            {
                "标题": document.title,
                "document_id": document.document_id,
                "问题数": document.question_count,
                "失败问题数": failed,
                "红线失败数": red,
                "状态": _document_status(document),
                "Overall Pass Rate": document.overall_pass_rate,
                "context_relevancy": document.metrics.context_relevancy,
                "source_coverage": document.metrics.source_coverage,
                "faithfulness": document.metrics.faithfulness,
                "answer_relevance": document.metrics.answer_relevance,
                "citation_validity": document.metrics.citation_validity,
                "refusal_appropriateness": document.metrics.refusal_appropriateness,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("没有符合筛选条件的文件")
        return

    event = st.dataframe(
        df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="file_table",
    )

    if event.selection.rows:
        selected_row = event.selection.rows[0]
        selected_doc_id = df.iloc[selected_row]["document_id"]
        _select_document(selected_doc_id)

    st.caption("表格选择会在选择后跳转；若排序导致选择丢失，请使用下方选择器兜底。")

    doc_ids = [""] + [row["document_id"] for _, row in df.iterrows()]
    index = 0
    if st.session_state.get("selected_document_id"):
        for i, doc_id in enumerate(doc_ids[1:], start=1):
            if doc_id == st.session_state.selected_document_id:
                index = i
                break

    def _format_doc_option(doc_id: str) -> str:
        if not doc_id:
            return ""
        matches = df[df["document_id"] == doc_id]
        if matches.empty:
            return doc_id
        row = matches.iloc[0]
        return f"{row['标题']} ({doc_id})"

    st.selectbox(
        "选择文件（兜底）",
        options=doc_ids,
        index=index,
        format_func=_format_doc_option,
        key="file_selectbox",
        on_change=_on_file_selectbox_change,
    )


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
