# W-S RAG 评测 Dashboard 实施计划分卷二：Streamlit 页面与状态

> 本分卷执行 Phase 2。Phase 1 loader 必须已经通过。

## Task 5：依赖预检与应用骨架

**依赖：** 需要 `streamlit>=1.58.0,<2.0`；若环境未安装，必须先按总览报备并取得用户确认。
**文件：**

- Create: `scripts/eval_ws_rag/dashboard.py`
- Create/Modify: `tests/eval_ws_rag/test_dashboard_app.py`

### Step 1：核对最新官方契约

在编码前只读取 Streamlit 官方文档，记录核验日期、安装版本和以下结论：

- 控件交互和 callback 的脚本重跑顺序；
- `st.session_state` 生命周期；
- `st.dataframe` 的 `on_select`、`selection_mode` 和排序后选择重置；
- `AppTest` 在 widget 修改后的显式 `.run()` 要求；
- `st.rerun()` 会立即终止当前运行，非必要不调用。

官方入口见 Dashboard 设计总览第 9 节。若已安装版本与文档不一致，停止并修订计划，不按记忆猜 API。

### Step 2：验证依赖

```bash
conda run -n fire python -c "import streamlit; print(streamlit.__version__)"
```

**预期输出：** 版本满足 `>=1.58.0,<2.0`。失败时停止，不得绕过 AppTest。

### Step 3：写页面失败测试

```python
def test_app_loads_local_tool_shell(): ...
def test_initial_load_builds_one_snapshot(): ...
def test_view_change_does_not_rescan_disk(): ...
```

使用 monkeypatch 统计 `build_snapshot` 调用次数。

### Step 4：运行并确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -k "shell or snapshot or rescan" -q
```

**预期输出：** FAIL，原因是 `dashboard.py` 尚不存在。

### Step 5：实现最小骨架

- `st.set_page_config` 设置本机评测工具标题；
- 初始化 `st.session_state.dashboard_snapshot`；
- 侧边栏创建 Run、视图和刷新控件；
- 主内容显示当前视图标题；
- 初始加载只构建一次快照；
- 用户文本不使用 `unsafe_allow_html=True`。

### Step 6：运行测试

**预期输出：** 骨架和快照测试 PASS。

### Step 7：提交 Task 5

```bash
git commit -m "feat(eval): 实现 Dashboard 应用骨架与会话状态"
```

## Task 6：TDD 实现总览和文件列表

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard.py`
- Modify: `tests/eval_ws_rag/test_dashboard_app.py`

### Step 1：写失败测试

```python
def test_overview_displays_report_values_without_regrading(): ...
def test_file_list_shows_text_status_and_metrics(): ...
def test_file_selection_updates_drilldown_state(): ...
def test_file_selectbox_is_available_as_selection_fallback(): ...
```

测试应使用故意与阈值重算结果不一致的 fixture，断言页面仍显示报告原值，以证明 Dashboard 没有重新判分。

### Step 2：确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -k "overview or file_list or file_selection" -q
```

**预期输出：** FAIL，原因是视图未实现。

### Step 3：实现总览

- `st.metric` 展示 summary；
- `st.dataframe` 展示六项指标与本轮阈值；
- `st.altair_chart` 展示文件状态分布；
- 失败原因和错误阶段按稳定 code 聚合；
- 不引入 Plotly。

### Step 4：实现文件列表

- `st.dataframe(on_select="rerun", selection_mode="single-row")`；
- 同时提供文件选择器兜底；
- 颜色和中文状态文本同时存在；
- 选择写入 session state 并切换问题下钻。

### Step 5：运行 AppTest

**预期输出：** Task 6 测试 PASS。每次修改 widget 后测试必须显式调用 `.run()`。

### Step 6：提交 Task 6

```bash
git commit -m "feat(eval): 实现 Dashboard 总览与文件视图"
```

## Task 7：TDD 实现问题下钻

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard.py`
- Modify: `tests/eval_ws_rag/test_dashboard_app.py`

### Step 1：写失败测试

```python
def test_drilldown_displays_scores_thresholds_and_failure_codes(): ...
def test_drilldown_displays_retrieved_chunks_and_bound_citations(): ...
def test_red_line_help_is_only_shown_near_active_failure(): ...
```

### Step 2：确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -k "drilldown or red_line" -q
```

**预期输出：** FAIL。

### Step 3：实现三栏视图

- 左栏：问题文本、类型、状态筛选；
- 中栏：`passed`、六项得分、阈值、失败对象、答案和拒答；
- 右栏：检索 chunk、分数、正文、被引用标记和结构化 citations；
- 只根据 `red_line_failures` 稳定代码映射中文说明；
- 不做字符串猜测或重新校验引文。

### Step 4：运行测试

**预期输出：** Task 7 测试 PASS。

### Step 5：提交 Task 7

```bash
git commit -m "feat(eval): 实现 Dashboard 问题下钻视图"
```

## Task 8：TDD 实现两轮对比

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard.py`
- Modify: `tests/eval_ws_rag/test_dashboard_app.py`

### Step 1：写失败测试

```python
def test_comparable_runs_show_deltas_and_file_transitions(): ...
def test_non_comparable_runs_show_reason_without_direction_claims(): ...
```

### Step 2：确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -k "comparable or non_comparable" -q
```

**预期输出：** FAIL。

### Step 3：实现同口径视图

- summary 和六指标差值；
- 文件状态变化；
- 被测系统变量差异；
- 新增失败与修复文件。

### Step 4：实现非同口径视图

- 并排元信息；
- 不一致字段；
- 原始 summary；
- 不渲染箭头、红绿变化和改进/退化文案。

### Step 5：运行测试

**预期输出：** Task 8 测试 PASS。

### Step 6：提交 Task 8

```bash
git commit -m "feat(eval): 实现 Dashboard 双轮对比视图"
```

## Task 9：TDD 实现显式刷新和错误状态

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard.py`
- Modify: `tests/eval_ws_rag/test_dashboard_app.py`

### Step 1：写失败测试

```python
def test_refresh_replaces_snapshot_atomically(): ...
def test_refresh_keeps_current_run_or_falls_back_to_latest(): ...
def test_invalid_run_shows_diagnostic_without_partial_content(): ...
def test_empty_catalog_shows_empty_state(): ...
```

### Step 2：确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -k "refresh or invalid_run or empty_catalog" -q
```

**预期输出：** FAIL。

### Step 3：实现刷新 callback

- callback 先完整构建新快照；
- 成功后一次替换 session state；
- 失败保留旧快照并显示错误；
- 使用 spinner；
- 不无条件调用 `st.rerun()`。

### Step 4：实现错误和空状态

- 文件缺失、JSON、schema、跨文件、跨字段分别提示；
- 不展示 traceback 或敏感 input snapshot；
- 空目录显示固定引导。

### Step 5：运行 Phase 2 测试

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -q
```

**预期输出：** 全部 PASS，无 warning、skip 或 xfail。

### Step 6：提交 Task 9

```bash
git commit -m "feat(eval): 完成 Dashboard 刷新和错误状态"
```
