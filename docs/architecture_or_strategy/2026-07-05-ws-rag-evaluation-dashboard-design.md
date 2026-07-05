# W-S RAG 评测 Dashboard 设计（数据契约分卷）

> 本文是 `docs/architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md` 的 Dashboard 扩展项专项设计。
> 当前仅冻结数据契约（第 1—3 节、第 7 节），信息架构、刷新策略、测试与依赖将在后续补充。

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

## 4. 信息架构与页面布局（待补充）

第 4 节将定义总览、文件列表、问题下钻、两轮对比四类视图的具体字段、筛选条件、空状态和红线失败呈现方式。当前尚未冻结，将在后续讨论后补充。

## 5. 刷新与错误处理（待补充）

第 5 节将定义显式刷新、报告发现、损坏 JSON、缺失字段、schema 不兼容、空目录和评测中间产物的用户提示。当前尚未冻结，将在后续讨论后补充。

## 6. 测试、验收与依赖（待补充）

第 6 节将定义单元测试、Streamlit AppTest、真实报告核对、浏览器烟雾验证的具体范围，并冻结 `streamlit` 版本范围和安装命令。当前尚未冻结，将在后续讨论后补充。

## 7. 与主评测设计文档的关系

- 主设计文档 `docs/architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md` 负责定义：评测范围、指标、LLM Judge、RAG Runner、校准策略；
- 本文负责定义：Dashboard 技术选型、数据契约、展示架构；
- 主设计文档第 8 节保留摘要和本文链接，具体 Dashboard 实现以本文为准。

## 8. 状态

- 数据契约：已冻结；
- 信息架构、刷新策略、测试与依赖：待补充；
- 能力状态：评测系统仍为 `planned`，Dashboard 作为其扩展项同步保持 `planned`。
