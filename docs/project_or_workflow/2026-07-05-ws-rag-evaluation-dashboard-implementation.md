# W-S RAG 评测 Dashboard 实施计划

> **执行状态：** 计划已批准，待按本计划进入开发。当前任务只编写计划，不实现 Dashboard 业务代码。
> **计划角色：** `project_or_workflow`（可执行入口）。

**目标：** 在 `fire` conda 环境下实现一个独立 Streamlit 本地 Dashboard，读取按轮次隔离的 `report.json` 与 `errors.json`，为开发者提供总览、文件列表、问题下钻和两轮对比四类只读视图。

**架构：** 单入口 Streamlit 应用（`scripts/eval_ws_rag/dashboard.py`），数据加载逻辑拆到同目录 `dashboard_loader.py` 以便单元测试；不改动 `app/` 核心服务，不新增后端 API。

**技术栈：** Python 3.14、Streamlit 1.58.0+、pytest、Pydantic（验证报告结构）、标准库 `pathlib`/`json`；全部命令通过 conda 环境 `fire` 执行。

---

## 1. 计划地位与权威依据

本文是“W-S RAG 评测 Dashboard”扩展项的可执行入口。它不替代设计；冲突时依次服从：

1. 根目录 `AGENTS.md`；
2. [工程技术标准](../architecture_or_strategy/工程技术标准.md)；
3. [Word/W 阶段单文件 RAG 问答评测设计](../architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md)；
4. [W-S RAG 评测 Dashboard 设计](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-design.md)；
5. 本计划及其可能拆分的分卷。

Dashboard 数据契约以 Dashboard 专项设计为准；评测主设计只保留扩展项摘要。

## 2. 里程碑范围

### 2.1 纳入范围

- 新建 `scripts/eval_ws_rag/` 目录（如尚未创建）；
- 实现 `scripts/eval_ws_rag/dashboard_loader.py`：
  - 发现 `reports/ws_rag_eval/` 下所有 Run 目录；
  - 按目录修改时间倒序排列；
  - 读取并校验 `report.json` / `errors.json`；
  - 提供文件级、问题级聚合与红线失败计数；
- 实现 `scripts/eval_ws_rag/dashboard.py`：
  - 左侧导航栏（Run 选择、四个视图入口、刷新按钮、当前 Run 元信息）；
  - 总览、文件列表、问题下钻、两轮对比四个视图；
  - 损坏 JSON、空目录的页面中间提示；
- 准备 `tests/eval_ws_rag/fixtures/mock_report.json` 与 `mock_errors.json`；
- 编写 `tests/eval_ws_rag/test_dashboard_loader.py`；
- 编写 `tests/eval_ws_rag/test_dashboard_app.py`（使用 Streamlit `AppTest`）；
- 执行浏览器烟雾测试；
- 同步文档索引与读取规则；
- 能力路线图保持 Dashboard 状态为 `planned`，直到真实评测报告跑通并通过人工核对。

### 2.2 不纳入范围

- 不实现启动评测、修改阈值、删除报告等写操作；
- 不实现实时文件监听或自动轮询；
- 不实现多用户、权限、云部署；
- 不改动现有 FastAPI 前端；
- 不在 Dashboard 中修复或重新生成损坏的报告；
- 不阻塞主评测链路的开发；Dashboard 可用 mock 数据先行开发。

## 3. 全局阶段输入检查

### 已确认

- Dashboard 专项设计已冻结（阶段 4—6 已完成）；
- Streamlit 1.58.0 官方已确认支持 Python 3.14；
- `streamlit>=1.58.0,<2.0` 已写入 `pyproject.toml`；
- 报告数据契约已冻结：`report.json` / `errors.json` 顶层结构、字段名、聚合方式；
- 页面布局与交互已冻结：左侧导航 + 四个视图 + 显式刷新；
- 错误处理已冻结：仅处理损坏 JSON 和空目录；
- 测试策略已冻结：mock 数据、单元测试、AppTest、浏览器烟雾测试、真实报告核对。

### 缺失输入

- 真实 `report.json` 尚未生成（依赖主评测链路），首版开发使用 mock 数据；
- 真实报告核对需等主评测链路首次跑通后由用户执行。

### 允许的默认值

- 报告根目录默认 `reports/ws_rag_eval/`；
- Run 显示名称为目录名；
- Run 按目录修改时间倒序排列；
- 无数据时所有视图显示“暂无数据”；
- 损坏 JSON 时不显示任何报告内容；
- 单元测试使用 fixtures 目录下的 mock 数据；
- AppTest 使用 `AppTest.from_file("scripts/eval_ws_rag/dashboard.py")`。

## 4. 依赖与包管理工具

| 环境 | 包管理工具 | 本计划处理 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；仅在获批后使用 `conda run -n fire python -m pip` | **新增 `streamlit>=1.58.0,<2.0`**，安装前再次向用户确认版本范围 |
| 测试 | `pytest`（已在 `dev` 可选依赖中） | 沿用现有环境 |
| 浏览器烟雾测试 | 可选 Playwright；不强制纳入自动化套件 | 如需安装，另行向用户确认 |
| 前端 | 不涉及 npm/pnpm/yarn | 无前端改动 |

**安装命令（需用户确认后执行）：**

```bash
conda run -n fire python -m pip install "streamlit>=1.58.0,<2.0"
```

执行中若发现必须新增其他依赖，应立即停止，列出依赖名称、用途、版本范围、安装位置和包管理工具，待用户确认后再修改计划并继续。

## 5. 分卷导航

本计划保持单卷，不拆分。Dashboard 代码量适中，单卷即可完整描述；若开发过程中发现超出 500 行，再按“数据加载/UI/测试”拆分为分卷。

## 6. 执行顺序

按以下 Phase 顺序执行；每个 Phase 通过对应测试后再进入下一 Phase。

| Phase | 任务 | 产出 |
| --- | --- | --- |
| Phase 1 | 搭建目录与 mock 数据 | `scripts/eval_ws_rag/`、`tests/eval_ws_rag/fixtures/`、mock JSON |
| Phase 2 | TDD 实现 `dashboard_loader.py` | 数据加载与聚合模块、单元测试 |
| Phase 3 | TDD 实现 `dashboard.py` 骨架与总览视图 | Streamlit 主入口、导航栏、总览 |
| Phase 4 | 实现文件列表、问题下钻、两轮对比视图 | 三个视图 + AppTest |
| Phase 5 | 刷新与错误处理 | 显式刷新、损坏 JSON 提示、空目录提示 |
| Phase 6 | 浏览器烟雾测试与文档收口 | 浏览器验证、文档索引更新、能力状态同步 |

### 6.1 Phase 1：搭建目录与 mock 数据

**目标：** 创建目录结构并准备覆盖主要场景的 mock 数据。

**新增文件：**

```text
scripts/eval_ws_rag/
├── __init__.py
├── dashboard.py          # Streamlit 入口
└── dashboard_loader.py   # 数据加载与聚合

tests/eval_ws_rag/
├── __init__.py
├── fixtures/
│   ├── mock_report.json
│   └── mock_errors.json
├── test_dashboard_loader.py
└── test_dashboard_app.py
```

**mock_report.json 覆盖场景：**

- 至少 2 份文件；
- 每份文件至少 3 个问题；
- 正常通过的问题；
- 指标低于阈值的问题；
- 三种红线失败各至少 1 例：引文无效、包含文件外内容、该拒答未拒答；
- 文件级 `metrics` 与 `overall_pass_rate` 手动计算正确，用于验证聚合逻辑。

**mock_errors.json 覆盖场景：**

- 空错误列表；
- 包含 1～2 条结构化错误。

### 6.2 Phase 2：TDD 实现 `dashboard_loader.py`

**目标：** 实现可独立测试的数据加载层。

**函数/类设计（建议）：**

| 名称 | 职责 |
| --- | --- |
| `RunRecord` (Pydantic dataclass) | 单个 Run 的目录路径、目录名、报告、错误报告 |
| `load_report(path)` | 读取 `report.json`，JSON 非法时抛 `ReportLoadError` |
| `load_errors(path)` | 读取 `errors.json`，JSON 非法时抛 `ReportLoadError` |
| `discover_runs(root_dir)` | 返回 `list[RunRecord]`，按目录 mtime 倒序 |
| `summarize_report(report)` | 返回总览需要的关键指标字典 |
| `aggregate_failure_reasons(report)` | 返回失败原因计数 |
| `is_red_line_failure(question)` | 判断单个问题是否存在红线失败 |
| `compute_metric_delta(baseline, current)` | 两轮对比的指标差异 |

**测试先行：**

1. 先写 `test_dashboard_loader.py` 中的失败测试；
2. 确认测试因能力缺失而失败；
3. 实现最小代码使测试通过；
4. 再补充下一个测试。

**单元测试覆盖：**

- 正常 `report.json` 解析；
- 损坏 JSON 抛出 `ReportLoadError`；
- Run 目录发现与排序正确；
- `overall_pass_rate` 聚合计算正确；
- 文件级指标聚合等于问题级指标平均；
- 红线失败判断正确；
- 空报告返回空摘要。

### 6.3 Phase 3：实现 `dashboard.py` 骨架与总览视图

**目标：** 让 Streamlit 应用能启动并展示总览。

**实现要点：**

- 使用 `st.set_page_config` 设置页面标题；
- 左侧栏使用 `st.sidebar`：
  - Run 下拉框（调用 `discover_runs`）；
  - 四个视图单选按钮；
  - 刷新按钮（调用 `st.rerun()` 或重新加载数据）；
  - 当前 Run 元信息（`run_id`、`created_at`、`judge_model`）；
- 主内容区根据 `view` 状态渲染；
- 总览视图：
  - `st.metric` 行展示文件数、问题总数、Overall Pass Rate、失败问题总数；
  - `st.dataframe` 展示指标均分表；
  - `st.plotly_chart` 或 `st.altair_chart` 绘制通过/失败环形图（优先使用 Streamlit 内置图表，避免新增依赖）；
  - 失败原因 Top 列表。

**AppTest 覆盖：**

- 页面能加载；
- Run 下拉框有选项；
- 切换视图后对应标题出现；
- 刷新按钮存在。

### 6.4 Phase 4：实现文件列表、问题下钻、两轮对比

**目标：** 完成剩余三个视图。

**文件列表视图：**

- `st.dataframe` 展示文件级表格；
- 支持排序、筛选；
- 行点击跳转通过 Streamlit 的 `st.session_state` 切换到问题下钻并选中文件。

**问题下钻视图：**

- 三栏布局：左问题列表、中问题详情、右检索证据；
- 使用 `st.columns([1, 2, 2])` 或类似比例；
- 列表只显示问题文本，通过/失败用颜色标识；
- 详情显示指标、失败原因、RAG 答案；
- 右侧显示召回 chunks 和引用条文；
- 红线失败时在详情卡片附近显示就近说明。

**两轮对比视图：**

- 两个 Run 下拉框（基准、对比）；
- 关键差异卡：Overall Pass Rate 变化、问题总数变化、失败问题数变化、三种红线问题变化数；
- 指标对比表；
- 文件级对比表，高亮新增失败和修复文件。

### 6.5 Phase 5：刷新与错误处理

**目标：** 显式刷新和两类错误提示。

**刷新实现：**

- 刷新按钮点击时：
  - 按钮置为 `disabled`；
  - 显示 `st.spinner("刷新中…")`；
  - 重新调用 `discover_runs`；
  - 如果当前选中的 Run 仍在列表中则保留选择；
  - 否则默认选择最新的 Run；
  - 使用 `st.rerun()` 刷新页面。

**损坏 JSON 处理：**

- 在页面中间（主内容区）使用 `st.error` 或自定义 Markdown 居中显示；
- 区分三种情况（见设计文档 5.3）；
- 不显示任何报告内容。

**空目录处理：**

- Run 下拉框显示“无可用报告”；
- 页面中间显示“你还没有任何评测结果，先去评测一下吧”。

### 6.6 Phase 6：浏览器烟雾测试与文档收口

**目标：** 验证真实浏览器表现并同步文档状态。

**浏览器烟雾测试步骤：**

1. 把 mock 数据复制到临时目录 `reports/ws_rag_eval/mock-run-20260705/`；
2. 启动 Dashboard：
   ```bash
   conda run -n fire streamlit run scripts/eval_ws_rag/dashboard.py
   ```
3. 用 Playwright 或手动访问 `http://localhost:8501`；
4. 检查：
   - 页面无报错；
   - 四个导航入口可点击；
   - 四个视图能正常切换；
   - 总览数字与 mock 数据一致。

**文档收口：**

- 更新 `docs/system_meta/文档索引.md` 注册本计划；
- 更新 [Dashboard 设计文档](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-design.md) 第 8 节状态，指向本计划；
- 能力路线图保持 Dashboard 为 `planned`，直到真实报告核对完成。

## 7. 全局硬门禁

1. 所有新增代码必须位于 `scripts/eval_ws_rag/` 和 `tests/eval_ws_rag/`，不得改动 `app/`；
2. `streamlit` 版本必须是 `>=1.58.0,<2.0`；
3. Run 显示名称必须是目录名，不得读取 `report.json` 中的 `run_id` 作为显示名；
4. Run 必须按目录修改时间倒序排列；
5. 任何 JSON 损坏时不得显示另一份文件的内容；
6. 无数据时所有视图必须显示“暂无数据”；
7. 红线失败说明必须遵守“就近说明”规则，不允许一次性列出所有红线规则；
8. 显式刷新，禁止自动轮询；
9. 单元测试必须覆盖正常解析、损坏 JSON、Run 发现排序、聚合计算；
10. AppTest 必须覆盖页面加载、Run 选择、视图切换、刷新按钮；
11. 浏览器烟雾测试必须通过；
12. 真实报告核对前，不得把 Dashboard 能力状态标记为 `implemented`；
13. 新增依赖必须经用户确认，禁止擅自安装。

## 8. 测试策略

### 8.1 单元测试

**命令执行意图：** 运行 Dashboard 加载器单元测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -q
```

**预期输出：** 全部 PASS。

### 8.2 AppTest

**命令执行意图：** 运行 Streamlit 应用测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -q
```

**预期输出：** 全部 PASS。

### 8.3 仓库回归

**命令执行意图：** 确保新增测试不破坏现有代码。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；不新增 warning、skip 或 xfail。

### 8.4 浏览器烟雾测试

**命令执行意图：** 启动 Dashboard 并验证页面无报错。

```bash
conda run -n fire streamlit run scripts/eval_ws_rag/dashboard.py
```

**预期输出：** 控制台无异常；浏览器访问 `http://localhost:8501` 后四个视图可切换。

## 9. Git 策略

本计划授权实施阶段在每个 Phase 完成对应测试后执行一次 `git add` 与 `git commit`：

| Phase | 中文 commit 说明 |
| --- | --- |
| Phase 1 | `chore(eval): 创建 Dashboard 目录与 mock 数据` |
| Phase 2 | `feat(eval): 实现 Dashboard 数据加载器与单元测试` |
| Phase 3 | `feat(eval): 实现 Dashboard 骨架与总览视图` |
| Phase 4 | `feat(eval): 实现文件列表、问题下钻与两轮对比` |
| Phase 5 | `feat(eval): 实现 Dashboard 刷新与错误处理` |
| Phase 6 | `docs(eval): 完成 Dashboard 烟雾测试与文档收口` |

- 每次提交只能包含当前 Phase 已验证的代码、测试、文档或配置；
- 提交前必须检查 `git diff --cached`，避开用户已有改动；
- 无法安全拆分用户改动时停止提交并报告；
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写。

**当前计划编写任务完成后可提交本计划文档。**

## 10. 里程碑完成定义

只有同时满足以下条件，才能把 Dashboard 扩展项标记为 `implemented`：

- `dashboard_loader.py` 能正确解析 mock 和真实 `report.json` / `errors.json`；
- `dashboard.py` 四个视图均可在浏览器中正常切换；
- 显式刷新、损坏 JSON 提示、空目录提示行为符合设计；
- 单元测试、AppTest、仓库回归全部通过；
- 浏览器烟雾测试通过；
- 用户用真实评测报告人工核对：总览数字、文件列表行数、问题下钻指标均与 JSON 一致；
- 文档索引、读取规则、能力路线图与真实状态一致；
- 主评测链路产出的真实报告格式与 Dashboard 数据契约一致。

计划完成、单元测试通过或 mock 数据验证通过，都不能单独视为里程碑完成。

## 11. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 真实报告格式与 mock 数据不一致 | Dashboard 无法展示真实结果 | 保持加载器与 Pydantic 模型校验解耦，真实报告跑通后补一轮真实核对 |
| Streamlit 在 Python 3.14 下出现运行时问题 | 无法启动 Dashboard | 安装前确认版本，发现问题立即回退并向用户报告 |
| 用户误把 Dashboard 当作生产前端 | 范围蔓延 | 在启动提示和文档中明确“本机调试工具，不对外服务” |
| AppTest 因 Streamlit 版本升级而失效 | CI 不稳定 | 锁定 `>=1.58.0,<2.0`，升级前重跑全部测试 |

## 12. 下一步

本计划获批后，按 Phase 1→Phase 6 顺序进入实现；每个 Phase 先写测试，再做最小实现，最后跑对应测试与回归。
