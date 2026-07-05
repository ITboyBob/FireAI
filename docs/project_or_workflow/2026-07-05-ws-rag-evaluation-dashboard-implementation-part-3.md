# W-S RAG 评测 Dashboard 实施计划分卷三：真实验证与收口

> 本分卷执行 Phase 3。开始前要求 Phase 1/2 全部测试通过，并且主评测链路已经发布真实 Run。

## Task 10：浏览器烟雾验证

**依赖：** 不新增 Python 或前端依赖。优先使用已有浏览器能力；若需要安装 Playwright，必须另行报备并取得确认。
**文件：**

- Modify: `tests/eval_ws_rag/`（仅当已有浏览器测试基础设施可复用）
- Record: 当前 Task 的验证记录或测试断言

### Step 1：启动本机服务

**意图：** 只在回环地址启动 Dashboard。

```bash
conda run -n fire python -m streamlit run scripts/eval_ws_rag/dashboard.py --server.address 127.0.0.1
```

**预期输出：** 控制台给出 `http://127.0.0.1:8501`，没有 import、schema 或端口错误。

### Step 2：检查关键路径

- 四类视图均可达；
- 文件表排序后仍可通过兜底选择器进入下钻；
- 三栏布局在目标桌面宽度下可读；
- 普通筛选不触发磁盘重新扫描；
- 显式刷新更新 Run 列表；
- 无报告和非法 Run 提示正确；
- 页面不显示 traceback、凭据或原始 JSON。

### Step 3：停止服务

结束浏览器验证后正常停止 Streamlit 进程，不遗留后台服务。

### Step 4：记录检查点

完成状态：浏览器关键路径通过；若只能人工验证，必须记录日期、环境、Run 和逐项结果，不得只写“页面正常”。

## Task 11：真实 Run 字段核对

**依赖：** 无需新增依赖；必须存在主评测链路正式发布的真实 Run。
**文件：**

- Read: `reports/ws_rag_eval/<run_id>/report.json`
- Read: `reports/ws_rag_eval/<run_id>/errors.json`
- Modify: 必要的测试 fixture 或验收记录

### Step 1：确认 Run 完整

**意图：** 验证真实 Run 通过共享 schema。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag -q
```

**预期输出：** 包含真实 Run 兼容性测试且全部 PASS。

### Step 2：人工抽查

至少核对：

- 顶层文件、问题、失败、红线和通过率；
- 一份文件的全部聚合字段；
- 一个通过问题；
- 一个普通失败问题；
- 一个红线失败问题；
- 检索 chunk 与 citation 绑定；
- 一条执行错误，若本轮无错误则用合法 errors fixture 验证页面。

### Step 3：核对同口径比较

需要第二个同 `dataset_fingerprint` 和 `protocol_fingerprint` 的真实 Run。检查：

- 页面允许差值；
- 文件和问题身份可对齐；
- 差值与两份 JSON 原值一致。

若没有第二个同口径 Run，Phase 3 未完成，不得用 mock 对比替代。

### Step 4：核对非同口径保护

选择不同数据集或协议 Run，确认页面只并排展示元信息，不输出方向结论。

### Step 5：记录检查点

完成状态：真实 Run 的 summary、文件、问题、证据、引文、错误和对比全部具有可追溯核对结果。

## Task 12：完整回归与文档状态收口

**依赖：** 无需新增依赖。
**文件：**

- Modify: `docs/architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-design.md`
- Modify: `docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md`
- Modify: `docs/system_meta/文档索引.md`
- Modify: `docs/system_meta/文档读取规则.md`
- Modify: `README.md`（仅当新增用户启动入口）

### Step 1：运行专项测试

```bash
conda run -n fire python -m pytest tests/eval_ws_rag -q
```

**预期输出：** 全部 PASS。

### Step 2：运行仓库完整回归

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS，不新增 warning、skip 或 xfail。

### Step 3：同步状态

只有 Task 10/11 和完整回归均通过时：

- Dashboard 能力更新为 `implemented`；
- 写入真实 Run ID、测试数量、浏览器验证和人工核对证据；
- 主评测系统仍按自己的完成定义单独判断，不能因 Dashboard 完成而自动升级；
- 索引和读取规则登记最终文档角色。

### Step 4：检查文档

**意图：** 检查空白错误、行数和断链。

```bash
git diff --check
```

**预期输出：** 无输出。

```bash
wc -l docs/architecture_or_strategy/*.md docs/project_or_workflow/*.md
```

**预期输出：** 所有 Markdown 不超过 500 行；本专项各卷保持低于 420 行预警线。

### Step 5：提交 Phase 3

```bash
git commit -m "docs(eval): 完成 Dashboard 真实报告验收与状态收口"
```

提交前必须确认只包含 Phase 3 已验证改动，不夹带用户文件。
