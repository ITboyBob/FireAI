# W-S RAG 评测 Dashboard 设计

> 本文是 `docs/architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md` 的 Dashboard 扩展项专项设计。
> 数据契约、信息架构、刷新策略、测试与依赖均已冻结。

## 1. 目标与范围

### 1.1 目标

为 Word/W 单文件 RAG 问答评测提供一份**本机只读 Dashboard**，让任何需要查看某次评测结果的人都能直接看到：

- 本轮评测的总体通过率和关键指标；
- 每份被测法规文件的评分卡；
- 每个合成问题的字段级得分与失败原因；
- 评测运行中产生的结构化错误；
- 两轮评测之间的指标差异。

### 1.2 范围边界

**首版做：**

- 独立 Streamlit 评测工作台；
- 读取按轮次隔离的 `report.json` 与 `errors.json`；
- 字段级指标展示，不展示原始 JSON；
- 总览、文件列表、问题下钻、两轮对比四类视图；
- 显式刷新按钮；
- 损坏/不兼容报告时的用户提示。

**首版不做：**

- 启动评测、修改阈值、删除报告；
- 实时文件监听、定时轮询、评测执行进度流；
- 多用户、权限、云部署；
- 与正式问答产品的前端导航集成。

### 1.3 使用者

首要使用者是**开发者 / 评测维护者**，核心任务是：比较轮次、定位失败 question、调试 Judge 和检索问题。

## 2. 技术选型

### 2.1 选定方案：独立 Streamlit 评测工作台

新增 `scripts/eval_ws_rag/dashboard.py`，运行后启动本地网页，读取 `reports/ws_rag_eval/<run_id>/report.json` 与 `errors.json`。

**选型理由：**

- 方向 A 需要大量表格、筛选、展开、对比，Streamlit 内置能力强；
- 不修改现有 FastAPI 产品前端，避免污染核心问答 UI；
- 开发速度最快，适合首版快速验证。

**主要代价：**

- 需要新增依赖 `streamlit`；
- 启动方式与现有服务不同：需单独运行 `streamlit run scripts/eval_ws_rag/dashboard.py`；
- 视觉风格与现有产品不一致。

### 2.2 未选方案说明

| 方案 | 未选原因 |
|---|---|
| 现有 FastAPI + Jinja2 新增 `/eval/dashboard` | 方向 A 的调试视图（多列排序、字段折叠、版本对比）手写成本高，会显著扩大前端代码量 |
| 每轮生成静态 HTML 报告 | 几乎无交互，无法满足下钻和两轮对比需求 |

### 2.3 依赖说明

- **新增依赖：** `streamlit`，版本范围待实施前根据官方 Python 3.14 兼容性再次核验；
- **安装环境：** `fire` conda 环境；
- **包管理工具：** `python -m pip`（读取 `pyproject.toml`）。

## 3. 数据契约

Dashboard 的唯一事实来源是每轮评测生成的 `report.json` 与 `errors.json`。

### 3.1 目录与写入规则

每轮评测生成不可覆盖的独立目录：

```text
reports/ws_rag_eval/<run_id>/
├── report.json
└── errors.json
```

**原子写入流程：**

1. 评测脚本先写入 `report.json.tmp` 与 `errors.json.tmp`；
2. 完成 JSON schema 自校验；
3. 原子重命名为正式文件；
4. Dashboard 只读取已通过校验的正式文件，遇到损坏报告时显示文件路径、错误原因和恢复建议，不静默跳过。

### 3.2 `report.json` 顶层结构

```json
{
  "schema_version": "1.0.0",
  "run_id": "ws-rag-eval-20260705-143022",
  "created_at": "2026-07-05T14:30:22+08:00",
  "git_commit": "a1b2c3d",
  "generation_model": "gpt-4o-mini",
  "judge_model": "gpt-4o-mini",
  "config": {
    "top_k": 5,
    "thresholds": {
      "context_relevancy": 0.6,
      "source_coverage": 0.8,
      "faithfulness": 0.8,
      "answer_relevance": 0.8,
      "citation_validity": 1.0,
      "refusal_appropriateness": 0.9
    }
  },
  "summary": {
    "document_count": 2,
    "question_count": 20,
    "failure_count": 3,
    "red_line_failure_count": 0,
    "overall_pass_rate": 0.85
  },
  "documents": [...],
  "errors": []
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `schema_version` | 报告格式版本，Dashboard 据此判断兼容性 |
| `run_id` | 本轮评测唯一标识 |
| `created_at` | 报告生成时间 |
| `git_commit` | 生成报告时仓库的 commit hash |
| `generation_model` | RAG 答案生成使用的模型 |
| `judge_model` | LLM Judge 使用的模型 |
| `config.top_k` | 检索阶段返回的候选 chunk 数量 |
| `config.thresholds` | 各指标通过阈值 |
| `summary` | 本轮全局统计 |

### 3.3 文件级评分卡（`documents[]`）

```json
{
  "document_id": "doc_xxx",
  "title": "消防监督检查规定",
  "source_path": "法律文本/todo/...",
  "question_count": 10,
  "failed_question_count": 1,
  "metrics": {
    "context_relevancy": 0.82,
    "source_coverage": 0.90,
    "faithfulness": 0.91,
    "answer_relevance": 0.88,
    "citation_validity": 1.0,
    "refusal_appropriateness": 0.90
  },
  "overall_pass_rate": 0.85,
  "questions": [...]
}
```

### 3.4 问题级明细（`documents[].questions[]`）

```json
{
  "question_id": "q-001",
  "question": "消防监督检查规定第十条规定了什么？",
  "question_type": "frequent",
  "source_chunk_id": "chunk_xxx",
  "answer": "...",
  "retrieved_chunk_ids": ["chunk_xxx", "chunk_yyy"],
  "citations": [...],
  "refused": false,
  "scores": {
    "context_relevancy": 0.9,
    "source_coverage": 0.85,
    "faithfulness": 0.92,
    "answer_relevance": 0.88,
    "citation_validity": 1.0,
    "refusal_appropriateness": 1.0
  },
  "passed": true,
  "failure_reasons": []
}
```

### 3.5 问题级与文件级指标聚合方式

问题级与文件级字段名相同，但聚合方式不同：

| 指标 | 问题级含义 | 文件级聚合方式 |
|---|---|---|
| `context_relevancy` | 单个问题的上下文相关性得分 | 该文件所有问题得分的算术平均 |
| `source_coverage` | 单个问题的来源覆盖率 | 该文件所有问题得分的算术平均 |
| `faithfulness` | 单个问题的忠实度 | 该文件所有问题得分的算术平均 |
| `answer_relevance` | 单个问题的答案相关性 | 该文件所有问题得分的算术平均 |
| `citation_validity` | 单个问题的有效引文比例 | 该文件所有问题有效引文比例的算术平均 |
| `refusal_appropriateness` | 单个问题是否正确处理拒答 | 该文件所有问题中正确处理的比例 |

`overall_pass_rate`（文件级）= 该文件中同时满足所有阈值的问题数 / 该文件总问题数。

报告顶层的 `overall_pass_rate` = 所有文件中通过的问题总数 / 所有问题总数。

### 3.6 `errors.json` 结构

`errors.json` 与 `report.json` 放在同一目录，并带相同头部：

```json
{
  "schema_version": "1.0.0",
  "run_id": "ws-rag-eval-20260705-143022",
  "created_at": "2026-07-05T14:30:22+08:00",
  "errors": [
    {
      "document_id": "doc_xxx",
      "question_id": "q-002",
      "stage": "vector_search",
      "stage_description": "向量检索阶段",
      "error_type": "FileNotFoundError",
      "message": "faiss.index not found",
      "recoverable": false,
      "input_snapshot": {
        "normalized_query": "...",
        "query_text_for_vector": "..."
      }
    }
  ]
}
```

`errors.json` 字段来源：

| 字段 | 来源 |
|---|---|
| `document_id` / `question_id` | 当前正在处理的文档和问题 |
| `stage` | 流水线阶段标识 |
| `stage_description` | 阶段标识到中文描述的映射 |
| `error_type` | Python 异常类名 |
| `message` | `str(exception)` |
| `recoverable` | 按错误类型判定：索引缺失等停止工作流；单个 question 解析异常则记录后继续 |
| `input_snapshot` | 出错时的查询文本、归一化结果等，用于复现 |

## 4. 信息架构与页面布局

### 4.1 页面骨架

左侧固定导航栏，右侧主内容区。

**导航栏：**

- 选择当前 Run（下拉框，列出 `reports/ws_rag_eval/` 下所有目录）。
- 四个视图入口：总览、文件列表、问题下钻、两轮对比。
- 刷新按钮。
- 底部显示当前 `run_id`、`created_at`、`judge_model`。

**主内容区：**

- 顶部：视图标题。
- 中间：数据内容。
- 无数据时：中间显示固定文字 **“暂无数据”**。

### 4.2 视图一：总览（Overview）

用途：一眼看清本轮评测全局结果。

| 元素 | 内容 |
|---|---|
| 关键数字卡 | 文件数、问题总数、Overall Pass Rate、失败问题总数 |
| 指标均分表 | 6 个指标本轮平均分，低于阈值标红 |
| 文件通过分布 | **环形图**：通过文件数 vs 失败文件数；旁边数字卡片显示具体数量 |
| 问题失败原因 Top | 按 `failure_reasons` 聚合，显示最常见的失败原因 |

通过标准：文件 `overall_pass_rate` ≥ 全局阈值。

空状态：中间显示 **“暂无数据”**。

### 4.3 视图二：文件列表（File List）

用途：定位哪些文件表现差。

**表格列：**

- 文件名 / 标题
- 问题数
- 失败问题数
- 状态（通过 / 失败 / 红线失败）
- Overall Pass Rate
- 6 个指标得分

**交互：**

- 点击表头按列排序。
- 顶部筛选：只看失败文件、只看某指标低于阈值的文件。
- 点击行跳转到“问题下钻”视图，并自动选中该文件。

**状态标记含义（页面底部图例）：**

- 绿色：通过。
- 黄色：失败（指标未达标，但无红线问题）。
- 红色：红线失败（存在引文无效、包含文件外内容、该拒答未拒答之一）。

空状态：中间显示 **“暂无数据”**。

### 4.4 视图三：问题下钻（Question Drill-down）

用途：看单个问题为什么失败。

**布局分三栏：**

- 左侧：问题列表
- 中间：问题详情
- 右侧：检索证据与答案

**左侧问题列表：**

- 只显示问题文本。
- 通过的问题用绿色标识，失败的用红色标识。
- 顶部筛选：只看失败问题、只看某类型问题。
- 点击问题，中间和右侧更新。

**中间问题详情：**

- 通过/失败状态。
- 6 个指标得分（表格上方标注：**标红 = 低于阈值**）。
- 失败原因列表。
- RAG 答案原文。

**右侧检索证据：**

- 召回的 chunk 列表。
- 每个 chunk 显示：chunk ID、相关性得分、是否被引用。
- 答案引用的条文列表。

**红线说明：** 如果当前问题存在红线失败，在详情卡片附近显示具体原因：

- “答案引用了检索证据中不存在的条文。”
- “答案包含当前文件外的内容。”
- “问题不可回答，但系统未拒答。”

空状态：中间显示 **“暂无数据”**。

### 4.5 视图四：两轮对比（Two-run Comparison）

用途：对比两个评测轮次，看优化是否有效。

**选择区：**

- 基准 Run（Baseline）。
- 对比 Run（Current）。

**关键差异卡：**

- Overall Pass Rate 变化（Current − Baseline）。
- 问题总数变化。
- 失败问题数变化。
- 三种红线问题各自的变化数：
  - 引文无效数变化。
  - 包含文件外内容数变化。
  - 该拒答未拒答数变化。

**指标对比表：**

| 指标 | 基准 Run | 对比 Run | 变化 |
|---|---|---|---|
| context_relevancy | 0.82 | 0.88 | +0.06 ↑ |
| ... | ... | ... | ... |

**文件级对比表：**

- 每个文件的通过率、各指标在两个 run 中的值。
- 失败文件（对比 run 新增失败）高亮。
- 修复文件（对比 run 从失败变通过）高亮。

**图例（页面旁边）：**

- 红色高亮：本轮新增失败文件。
- 绿色高亮：本轮修复文件。

不展示问题级差异。

空状态：中间显示 **“暂无数据”**。

### 4.6 红线高亮的就近说明规则

Dashboard 中不允许一次性列出所有红线规则。规则是：

- 只有当当前视图/表格/卡片里**实际出现了某种红线高亮**时，才在附近显示该高亮的含义。
- 含义用简短一句话，紧邻高亮元素出现。

例如：

- 文件列表中某行状态为“红线失败” → 该行附近或底部图例显示“红线失败 = 存在引文无效、包含文件外内容、或该拒答未拒答”。
- 问题详情中某问题引文无效 → 该问题得分卡片旁显示“答案引用了检索证据中不存在的条文”。

## 5. 刷新与错误处理

### 5.1 刷新机制

Dashboard 采用**显式刷新**，不自动轮询。

- 刷新按钮放在左侧导航栏（已在 4.1 定义）。
- 点击后重新扫描 `reports/ws_rag_eval/` 目录，重新加载当前选中的 `report.json` 和 `errors.json`。
- 刷新期间按钮变为不可点击，显示“刷新中…”。
- 刷新完成后，如果 Run 列表发生变化，下拉框同步更新。

### 5.2 报告发现

- Dashboard 启动时读取 `reports/ws_rag_eval/` 下所有一级子目录。
- 每个子目录被视为一个 Run。
- **Run 显示名称必须显示该文件夹的名字**，不读取 `report.json` 中的 `run_id`。
- Run 按目录修改时间倒序排列，最新的在最上面。

### 5.3 损坏 JSON 处理

Dashboard 只读取 `.json` 正式文件。如果文件不是合法 JSON，按以下情况在**页面中间**显示提示：

| 情况 | 页面中间提示 |
|---|---|
| `report.json` 和 `errors.json` 都损坏 | **结果和错误报告格式均有误，请检查** |
| 仅 `report.json` 损坏 | **结果报告格式有误，请检查** |
| 仅 `errors.json` 损坏 | **错误报告格式有误，请检查** |

任一文件损坏时，Dashboard 都不显示另一份文件的内容。

### 5.4 空目录处理

如果 `reports/ws_rag_eval/` 目录不存在或为空：

- Run 下拉框显示“无可用报告”。
- 页面中间显示：**你还没有任何评测结果，先去评测一下吧**。

## 6. 测试、验收与依赖

### 6.1 依赖

- **新增依赖：** `streamlit`
- **版本范围：** `>=1.58.0,<2.0`
  - 官方 `pyproject.toml` 已确认 `requires-python = ">=3.10"`，且 classifiers 包含 `Programming Language :: Python :: 3.14`，与本仓库 Python 3.14 约束兼容。
- **安装环境：** `fire` conda 环境
- **包管理工具：** `python -m pip`
- **安装命令：**
  ```bash
  conda run -n fire python -m pip install "streamlit>=1.58.0,<2.0"
  ```

### 6.2 Mock 数据

为烟雾测试和单元测试提前准备一份 mock 数据，避免依赖真实评测结果。

**存放位置：**

```text
tests/eval_ws_rag/fixtures/
├── mock_report.json
└── mock_errors.json
```

**mock 数据覆盖场景：**

- 正常通过的问题
- 指标低于阈值的问题
- 红线失败的问题（引文无效、包含文件外内容、该拒答未拒答）
- 空错误列表
- 包含错误的场景

### 6.3 单元测试

- 放在 `tests/eval_ws_rag/test_dashboard_loader.py`。
- 覆盖：
  - 正常 `report.json` 解析
  - 损坏 JSON 的异常抛出
  - 指标聚合计算正确
  - Run 目录发现排序正确

### 6.4 Streamlit AppTest

- 放在 `tests/eval_ws_rag/test_dashboard_app.py`。
- 使用 `AppTest.from_file("scripts/eval_ws_rag/dashboard.py")`。
- 覆盖：
  - 页面能加载
  - Run 下拉框能选择
  - 切换视图后对应元素出现
  - 刷新按钮能点击

### 6.5 浏览器烟雾测试

- 在 `fire` 环境中执行：
  ```bash
  conda run -n fire streamlit run scripts/eval_ws_rag/dashboard.py
  ```
- 使用 mock 数据作为默认加载报告。
- 用 Playwright 或手动访问 `http://localhost:8501`。
- 检查：
  - 页面无报错
  - 四个导航入口可点击
  - 总览、文件列表、问题下钻、两轮对比四个视图能正常切换

### 6.6 真实报告核对（用户执行）

- 在评测脚本首次完整跑通后，由用户用生成的真实 `report.json` 打开 Dashboard。
- 人工核对：
  - 总览数字与 JSON 中的 `summary` 一致
  - 文件列表行数与 `documents` 长度一致
  - 问题下钻的指标与 JSON 中对应问题一致

### 6.7 验收标准

- [ ] `streamlit>=1.58.0,<2.0` 已写入 `pyproject.toml`。
- [ ] mock 数据文件已创建并覆盖主要场景。
- [ ] 单元测试通过。
- [ ] Streamlit AppTest 通过。
- [ ] 浏览器烟雾测试通过。
- [ ] 用户完成真实报告核对。

## 7. 与主评测设计文档的关系

- 主设计文档 `docs/architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md` 负责定义：评测范围、指标、LLM Judge、RAG Runner、校准策略；
- 本文负责定义：Dashboard 技术选型、数据契约、展示架构；
- 主设计文档第 8 节保留摘要和本文链接，具体 Dashboard 实现以本文为准。

## 8. 状态

- 数据契约、信息架构、刷新策略、测试与依赖：已冻结；
- `streamlit>=1.58.0,<2.0` 已同步写入 `pyproject.toml`；
- 能力状态：评测系统仍为 `planned`，Dashboard 作为其扩展项同步保持 `planned`；
- SDD/TDD 实施计划已写入 [W-S RAG 评测 Dashboard 实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-dashboard-implementation.md)，获批后按 Phase 1—6 进入开发。
