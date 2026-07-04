# Word/W 阶段单文件 RAG 问答评测设计

**版本：** 1.0  
**日期：** 2026-07-04  
**设计文档状态：** 已形成 1.0 版；Linear `BOB-20` 正在继续完成设计与执行计划编写

**能力状态：** `planned`；尚无评测执行计划、业务代码、自动化测试或真实文件评测结果，不能标记为已实现

**Linear 进度快照：** 2026-07-04 里程碑“建立并完成Word文档的评测系统”为 25%，当前唯一附属 issue `BOB-20` 状态为 `In Progress`

## 1. 设计目标

为已导入的 Word/W 阶段法规文件建立一套**端到端 RAG 问答评测**能力：

- **端到端**：从用户问题出发，经过真实检索和真实答案生成，再评价结果。
- **无参考答案（Reference-free）**：不依赖人工编写的标准答案，用 LLM Judge 和规则校验打分。
- **单文件粒度**：每份 Word 文件独立生成问题、独立跑评测、独立产出评分卡，便于定位是哪份文件导入后影响问答效果。
- **不污染核心代码**：所有评测代码放在 `scripts/eval_ws_rag/` 和 `scripts/evaluate_ws_rag.py`，不改动 `app/` 下核心服务代码。

本设计复用现有 `app/services/retriever.py`、`app/services/answer_service.py` 和 `app/services/chat_client.py`，只读调用、不修改行为。

## 2. 评测设计链路

本设计直接映射知识库中的评测链路：

> **Task → Dataset → Rubric + Metric → Judge/Protocol → 运营评测**

### 2.1 Task：能力边界

- **测**：单份 Word 法规文件导入后，用户基于该文件提问，系统能否正确检索并回答。
- **不测**：多文件联合推理、跨法规对比、PDF/扫描件、模型通用法律知识。
- **安全底线**：回答必须能回溯到当前文件条文，不得自由发挥。

### 2.2 Dataset：三类问题分层

每份 Word 文件的问题集覆盖三层场景，目标是**场景覆盖率**而非题目数量：

| 层级 | 说明 | 示例 |
|---|---|---|
| 高频场景 | 用户最可能问的常规事实性问题 | “消防监督检查规定第十条规定了什么？” |
| 高风险/边界场景 | 容易出错的边界情况 | 问一个文件中不存在的条文，测试是否 hallucinate |
| 多样性切片 | 覆盖文件不同结构位置 | 开头总则、中间条款、尾部附则各出题 |

### 2.3 Rubric + Metric

#### Rubric 三层结构

| 层级 | 含义 | 本次映射 |
|---|---|---|
| 红线 | 一票否决 | 引文无效、包含文件外杜撰内容、该拒答时不拒答 |
| 质量维度 | 必须过关的核心指标 | 忠实度 ≥ 阈值、上下文相关性 ≥ 阈值 |
| 体验偏好 | 加分项/细节优化 | 答案是否简洁、是否给出法条原文摘要 |

#### Metric 仪表盘指标

| 指标 | 类型 | 用途 |
|---|---|---|
| Pass Rate | 通过率 | 多少合成问题通过所有红线+质量维度 |
| Likert 均分 | 均分 | 每个质量维度的平均得分 |
| Win Rate | 胜负率 | 两个版本系统对比时，哪个版本赢 |

### 2.4 Judge / Protocol

#### Judge 类型

| Judge 类型 | 用途 | 本次设计 |
|---|---|---|
| 规则程序 | 引文格式、引用是否在证据中 | 复用现有 `answer_service` 引文校验 |
| LLM-as-a-Judge | 忠实度、答案相关性、上下文相关性 | 独立 `ChatClient` 调用模型打分 |
| 人工评审 | 校准阶段 | 抽查 50～100 条合成问答确定阈值 |
| 专家评审 | 法律语义争议 | 对红线误判或边界案例做最终裁决 |

#### Evaluation Protocol（第一阶段）

- **模型版本**：固定 Judge 模型版本，写入配置。
- **盲评**：Judge 不知道被测的是哪个版本/文件。
- **校准频率**：换模型版本或换提示词后必须重新校准阈值。

#### LLM Judge 偏见对冲

| 偏见 | 通俗解释 | 对冲方法 |
|---|---|---|
| 位置偏见 | LLM 更偏向先看到的证据 | 随机打乱证据顺序，多次打分取平均 |
| 冗长偏见 | 答案越长越容易得高分 | Prompt 明确“不看长度，只看依据” |
| 自我偏好 | LLM 更喜欢自己生成的内容 | Judge 模型和生成模型尽量不同 |

### 2.5 运营评测闭环

```
线上 bad case → 脱敏打标 → 进入 eval 库 → 分析失分 → 优化导入/检索/生成 → 新版本验证
```

- **离线-线上拟合**：离线 Pass Rate 高但线上用户不满意，说明评测集失真，需补样本。
- **Goodhart 定律**：不要只优化单一指标，防止系统“刷分”。
- **熔断机制**：关键指标下降超过阈值时，阻断发布。

## 3. 评测指标定义

### 3.1 检索层指标

#### 上下文相关性（Context Relevancy）

**定义**：召回的 top-k chunks 中，对回答问题有用的比例。

**计算**：

```
对每个召回 chunk，LLM Judge 回答：
"这个片段对回答问题 '{question}' 是否有帮助？" Yes / No

Context Relevancy = Yes 数 / 总召回 chunk 数
```

**阈值**：≥ 0.8 通过，0.6～0.8 警告，< 0.6 失败。

#### 来源覆盖率（Source Coverage）

**定义**：回答问题所需条文是否都被检索到。

**计算**：

```
1. 使用合成问题附带的 expected_article 作为关键条文。
2. 检查检索结果是否包含该条文对应的 chunk。
3. 包含 → 覆盖成功；否则 → 覆盖失败。
```

**阈值**：关键条文召回率 ≥ 0.9 通过。

### 3.2 生成层指标

#### 忠实度（Faithfulness）

**定义**：答案里的每个断言都能在检索到的 evidence 中找到支持。

**计算**：

```
1. 把答案拆成 claims。
2. 对每个 claim，LLM Judge 判断：
   "该断言是否被给定证据支持？" supported / not_supported / unknown
3. Faithfulness = supported 数 / 总 claim 数
```

**阈值**：≥ 0.9 通过（法律场景要求严格）。

#### 答案相关性（Answer Relevance）

**定义**：答案是否真正回应问题。

**计算**：

```
LLM Judge 回答：
"这个答案对问题 '{question}' 的直接有用程度是多少？" 1-5 分

Answer Relevance = 平均分 / 5
```

**阈值**：≥ 0.8 通过。

#### 引文有效性（Citation Validity）

**定义**：答案引用的法规名和条号必须真实存在于检索证据中。

**计算**：

```
Citation Validity = 有效引文数 / 总引文数
```

**阈值**：= 1.0 通过。

#### 拒答适当性（Refusal Appropriateness）

**定义**：该回答时回答，不该回答时拒答。

**计算**：

| 问题类型 | 期望行为 | 判断方式 |
|---|---|---|
| 可回答问题 | 必须给出结论 | 结论不是拒答结论 |
| 不可回答问题 | 应拒答 | 结论是拒答，且 uncertainty 合理 |

```
拒答适当性 = 正确处理的 question 数 / 总 question 数
```

**阈值**：≥ 0.9 通过。

### 3.3 综合通过率

```
Overall Pass Rate = 同时满足以下条件的 question 数 / 总 question 数
  - 上下文相关性 ≥ 阈值
  - 忠实度 ≥ 阈值
  - 答案相关性 ≥ 阈值
  - 引文有效性 = 1.0
  - 拒答适当性正确
```

## 4. 整体架构与数据流

### 4.1 流程图

```
单份 Word 文件
    │
    ▼
读取已导入 chunks
    │
    ▼
合成问题生成器
    │
    ▼
真实 RAG 问答 pipeline
（Retriever.search + answer_service.build_answer）
    │
    ▼
LLM Judge + 规则校验
    │
    ▼
聚合每文件评分卡 + 报告
```

### 4.2 组件职责

所有组件放在 `scripts/eval_ws_rag/` 下：

| 组件 | 文件 | 职责 |
|---|---|---|
| Question Generator | `scripts/eval_ws_rag/question_generator.py` | 从 chunk 生成合成问题 |
| RAG Runner | `scripts/eval_ws_rag/rag_runner.py` | 调用真实检索+生成 |
| LLM Judge | `scripts/eval_ws_rag/llm_judge.py` | 对检索和生成结果打分，可切换模型 |
| Rule Validator | `scripts/eval_ws_rag/rule_validator.py` | 引文、JSON、拒答等规则校验 |
| Report Aggregator | `scripts/eval_ws_rag/report_aggregator.py` | 聚合评分卡 + 报告 |
| 入口 CLI | `scripts/evaluate_ws_rag.py` | 用户入口 |

### 4.3 LLM Judge 模型切换

LLM Judge 使用独立的 `ChatClient` 实例，和 RAG Runner 的答案生成模型解耦。通过配置文件或 CLI 参数指定 Judge 模型：

```bash
conda run -n fire python scripts/evaluate_ws_rag.py \
  --data-dir data \
  --document-id doc_xxx \
  --judge-model gpt-4o-mini \
  --output reports/ws_rag_eval.json
```

## 5. 核心数据结构

### 5.1 合成问题

```json
{
  "question": "消防监督检查规定第十条规定了什么？",
  "expected_article": "第十条",
  "question_type": "frequent",
  "source_chunk_id": "chunk_xxx",
  "answer_sketch": "规定公安机关消防机构应定期..."
}
```

### 5.2 RAG Runner 输出

```json
{
  "question": "...",
  "retrieved_chunks": [...],
  "answer": "...",
  "citations": [...],
  "refused": false,
  "uncertainty": null
}
```

### 5.3 每文件评分卡

```json
{
  "document_id": "doc_xxx",
  "title": "消防监督检查规定",
  "question_count": 10,
  "metrics": {
    "context_relevancy": 0.82,
    "source_coverage": 0.90,
    "faithfulness": 0.91,
    "answer_relevance": 0.88,
    "citation_validity": 1.0,
    "refusal_appropriateness": 0.90
  },
  "overall_pass_rate": 0.85,
  "failed_questions": [...]
}
```

## 6. 错误处理

### 6.1 Judge LLM 调用失败

- **处理**：整个工作流停止，进入 Debug 阶段。
- **输出**：记录失败时的 question、prompt 摘要、模型版本、异常信息。
- **退出码**：`1`

### 6.2 RAG Runner 检索失败

记录结构化错误信息到 `reports/ws_rag_eval_retrieval_errors.json`：

```json
{
  "question": "...",
  "stage": "vector_search",
  "stage_description": "向量检索阶段",
  "object": {
    "document_id": "doc_xxx",
    "data_dir": "data",
    "keyword_db_path": "data/index/retrieval.db",
    "vector_index_path": "data/index/faiss.index",
    "vector_map_path": "data/index/vector_map.json",
    "top_k": 5
  },
  "error": {
    "type": "FileNotFoundError",
    "message": "faiss.index not found",
    "traceback": "..."
  },
  "input_snapshot": {
    "normalized_query": "...",
    "query_text_for_vector": "..."
  },
  "recoverable": false
}
```

### 6.3 检索失败阶段分类

| 阶段 | 组件 | 典型失败原因 |
|---|---|---|
| query_normalization | `normalize_query()` | 查询解析失败、日期/地区格式异常 |
| keyword_search | `search_keyword_index()` | `retrieval.db` 缺失、SQL 错误 |
| vector_encoding | `_encode_queries()` | embedder 未提供、接口不兼容 |
| vector_search | `FaissVectorStore.search()` | `faiss.index` 缺失、维度不匹配 |
| result_fusion | `fuse_results()` | 分数归一化异常、权重非法 |

### 6.4 失败处理策略

| 失败类型 | 处理 |
|---|---|
| 索引文件缺失、embedder 未配置 | 停止整个工作流 |
| 单个 question 查询格式异常 | 记录后继续下一个 question，标记 invalid_question |
| 某 question 召回为空 | 不算失败，正常进入生成阶段测试拒答 |
| 结果融合异常 | 停止工作流 |

## 7. 测试与校准

### 7.1 测试策略

| 测试类型 | 目的 |
|---|---|
| 单元测试 | 确保 `question_generator`、`rule_validator`、`report_aggregator` 独立可用 |
| 集成测试 | 用一份小文件跑一次完整 `scripts/evaluate_ws_rag.py` |
| 真实验证 | 用 W-S1/W-S2 真实文件跑评测，人工抽查 10% |

### 7.2 校准工作流

1. 选 Judge 模型版本。
2. 对 1～2 份已知文件跑评测，得到原始分数。
3. 人工抽查 20 条 Judge 打分结果。
4. 根据抽查结果调整阈值。
5. 把阈值、模型版本写入 `scripts/eval_ws_rag/config.json`。
6. 换模型版本时重新执行 2～5 步。

### 7.3 基线管理

- 第一次完整跑通后，保存 `reports/baseline.json`。
- 后续每次跑评测都和 baseline 做 diff。

## 8. 扩展项：前端 Dashboard

### 8.1 目标

把每一轮 eval 结果除了写入 JSON report 外，还填入一份固定的前端 Dashboard，方便直接查看数据，无需手动解析 JSON。

### 8.2 设计原则

- 不引入新的前端框架，复用现有 FastAPI 模板和静态资源。
- Dashboard 是只读展示，不修改核心 RAG 服务。
- 每次评测运行后自动刷新 Dashboard 数据。

### 8.3 初步思路

1. **数据写入**：`report_aggregator.py` 在生成 JSON 后，同时生成一份 `reports/ws_rag_eval_dashboard.json`，结构面向前端展示优化。
2. **页面路由**：新增一个只读页面，例如 `/eval/dashboard`，由 FastAPI 渲染模板并读取 dashboard JSON。
3. **展示内容**：
   - 总体 Pass Rate 趋势图
   - 每份文件的评分卡列表
   - 失败问题详情
   - 检索错误统计
4. **后续细化**：Dashboard 的具体布局、图表库选择、刷新机制在实现阶段单独设计。

## 9. 依赖

- 无需新增依赖，沿用现有 `fire` conda 环境。
- LLM Judge 复用现有 `openai` 客户端和 `ChatClient` 协议。

## 10. 验收标准

- [ ] 能对单份 Word 文件生成合成问题。
- [ ] 能调用真实 RAG pipeline 并得到检索/生成结果。
- [ ] LLM Judge 能产出上下文相关性、忠实度、答案相关性分数。
- [ ] 规则校验能正确判断引文有效性和拒答适当性。
- [ ] 能产出每文件评分卡和总报告 JSON。
- [ ] Judge LLM 调用失败时工作流停止并输出 Debug 信息。
- [ ] RAG Runner 检索失败时记录结构化错误信息。
- [ ] 在 `fire` 环境下完整跑通 W-S1/W-S2 各一份文件。
