# Word/W 阶段单文件 RAG 问答评测设计

**版本：** 1.0  
**日期：** 2026-07-04  
**设计文档状态：** 已形成 1.0 版；对应“总览 + 3 分卷”执行计划已建立

**能力状态：** `planned`；执行计划已建立，但尚无业务代码、自动化测试或真实文件评测结果，不能标记为已实现

**执行入口：** [Word/W 单文件 RAG 问答评测实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-implementation.md)

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

首轮固定评测两份已导入法规：W-S1 的 `doc_d97773f1500c`《消防监督检查规定》和 W-S2 的 `doc_0e84d13a099b`《河北省消防设施管理规定》。前者验证纯正文法规，后者验证正文前含发布材料时仍能围绕目标法规检索和回答；两份文件不是训练数据。

每份 Word 文件的问题集覆盖三层场景，默认每类 1 条、每份文档共 3 条：

| 层级 | 说明 | 示例 |
|---|---|---|
| 高频场景 | 用户最可能问的常规事实性问题 | “消防监督检查规定第十条规定了什么？” |
| 高风险/边界场景 | 容易出错的边界情况 | 问一个文件中不存在的条文，测试是否 hallucinate |
| 多样性切片 | 覆盖文件不同结构位置 | 开头总则、中间条款、尾部附则各出题 |

三类数量分别由环境变量配置。首轮合计仅 6 条问题，只用于证明评测链路和两类文档边界能够端到端运行，不足以形成统计意义上的模型质量结论。

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
| 人工评审 | 不纳入首轮范围 | 不执行人工校准，不据此宣称 Judge 与法律专家一致 |

#### Evaluation Protocol（第一阶段）

- **模型版本**：答案生成使用现有 `CHAT_*`；问题生成和 Judge 使用各自独立环境变量，精确模型版本写入 dataset 和报告。
- **盲评**：Judge 不知道被测的是哪个版本/文件。
- **调用策略**：问题生成、答案生成和 Judge 全部串行；每次失败后最多额外重试 1 次。
- **阈值边界**：首轮沿用设计默认阈值，但因不做人工校准，只能作为工程门禁，不能解释为经专家验证的法律质量标准。

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
  - 来源覆盖率 ≥ 阈值
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
| Dataset Store | `scripts/eval_ws_rag/dataset_store.py` | 固化问题集、来源和指纹，禁止评测时临时重生成 |
| RAG Runner | `scripts/eval_ws_rag/rag_runner.py` | 调用真实检索+生成 |
| LLM Judge | `scripts/eval_ws_rag/llm_judge.py` | 对检索和生成结果打分，可切换模型 |
| Rule Validator | `scripts/eval_ws_rag/rule_validator.py` | 引文、JSON、拒答等规则校验 |
| Report Aggregator | `scripts/eval_ws_rag/report_aggregator.py` | 聚合评分卡 + 报告 |
| Report Publisher | `scripts/eval_ws_rag/report_publisher.py` | 校验并以 Run 目录为单位原子发布报告 |
| Dataset CLI | `scripts/generate_ws_rag_dataset.py` | 独立生成不可变问题集 |
| Evaluation CLI | `scripts/evaluate_ws_rag.py` | 只读取已固化 dataset 执行评测 |

### 4.3 模型配置与切换

三类模型不再通过 CLI 参数选择，统一在启动前由环境变量冻结：

- 答案生成：沿用 `CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL`；
- 问题生成：`WS_RAG_QUESTION_GENERATOR_API_KEY`、`WS_RAG_QUESTION_GENERATOR_BASE_URL`、`WS_RAG_QUESTION_GENERATOR_MODEL`，首轮模型为 `deepseek-v4-pro-260425`；
- Judge：`WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL`、`WS_RAG_JUDGE_TEMPERATURE`，首轮模型为 `doubao-seed-2-1-pro-260628`、温度为 `0`；
- 三类调用共用 `WS_RAG_MODEL_MAX_RETRIES=1`，含首次调用最多尝试 2 次；编排器不得并发调用模型。

问题生成和 Judge 的 Key、URL 首轮取值与现有 `CHAT_API_KEY`、`CHAT_BASE_URL` 相同，但仍使用独立变量，便于以后分别切换。LLM Judge 使用独立结构化客户端，不复用在线回答固定的 `ModelAnswer` schema。问题集生成和评测执行仍是两个独立阶段：

```bash
conda run -n fire python scripts/generate_ws_rag_dataset.py --help
conda run -n fire python scripts/evaluate_ws_rag.py --help
```

dataset CLI 必须传入目标文档、dataset ID 和 seed；评测 CLI 必须传入已落盘 dataset 和 Run ID。两者从环境读取模型配置，不接受模型选择参数，也不得通过评测 CLI 的 `--document-id` 隐式生成临时问题集。

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

正式 Run 还必须记录 `schema_version`、dataset/protocol 双指纹、被测系统版本、稳定失败代码、完整检索证据和结构化引文。共享完整契约见 [Dashboard 数据契约](./2026-07-05-ws-rag-evaluation-dashboard-data-contract.md)，写入器与 Dashboard loader 必须复用同一 `report_models.py`。

## 6. 错误处理

### 6.1 Judge LLM 调用失败

- **处理**：整个工作流停止，进入 Debug 阶段。
- **输出**：记录失败时的 question、prompt 摘要、模型版本、异常信息。
- **退出码**：`1`

### 6.2 RAG Runner 检索失败

可恢复的单问题错误写入 `reports/ws_rag_eval/<run_id>/errors.json`；致命错误停止正式 Run 发布，并把脱敏调试信息写入 `var/ws_rag_eval/<run_id>/debug.json`。`report.json` 与 `errors.json` 必须在同一暂存目录通过共享 schema 和跨字段校验后，以一次目录重命名发布。

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

## 7. 测试、限制与基线

### 7.1 测试策略

| 测试类型 | 目的 |
|---|---|
| 单元测试 | 确保 `question_generator`、`rule_validator`、`report_aggregator` 独立可用 |
| 集成测试 | 真实索引 + fake 模型验证确定性链路，不访问外部模型 |
| 真实验证 | 显式运行真实生成模型和独立 Judge，再用只读验证器核对 W-S1/W-S2 联合 Run |

### 7.2 首轮限制声明

- 首轮不执行人工校准或专家裁决；
- 默认阈值和 Judge 分数只用于工程回归，不代表法律专业准确率；
- dataset、报告和 Dashboard 必须展示 `judge_calibrated=false`，防止使用者把未校准分数误认为专家结论；
- 未来若要把分数用于发布决策，必须另立人工校准计划，不能静默提高本轮证据等级。

### 7.3 基线管理

- baseline registry 保存到 `data/eval/ws_rag_baselines.json`，只引用不可变正式 Run。
- 首个通过真实验收的 Run 只登记为 baseline；本轮不生成第二个 current Run，也不输出模型改进结论。
- 只有 schema 主版本、dataset、protocol 及文档/问题身份全部一致时才能输出方向性差异。

## 8. 扩展项：前端 Dashboard

Dashboard 扩展项已拆分为独立[专项设计](./2026-07-05-ws-rag-evaluation-dashboard-design.md)与[实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-dashboard-implementation.md)。

本文仅保留原初目标：把每一轮 eval 结果以只读方式展示在本地 Dashboard 中，方便直接查看数据，无需手动解析 JSON。具体的技术选型、数据契约、展示架构、刷新策略、测试与依赖均以后续专项设计为准。

## 9. 依赖

- 无需新增依赖，沿用现有 `fire` conda 环境。
- 三类模型复用现有 `openai` SDK；答案生成沿用 `CHAT_*`，问题生成和 Judge 使用独立环境变量及结构化响应适配器。

## 10. 验收标准

- [ ] 能对单份 Word 文件生成合成问题。
- [ ] 能把问题集独立固化为带 dataset ID 和 fingerprint 的不可变产物。
- [ ] 能调用真实 RAG pipeline 并得到检索/生成结果。
- [ ] LLM Judge 能产出上下文相关性、忠实度、答案相关性分数。
- [ ] 规则校验能正确判断引文有效性和拒答适当性。
- [ ] 能产出每文件评分卡和总报告 JSON。
- [ ] 能以 Run 目录为单位原子发布 `report.json` 与 `errors.json`。
- [ ] Judge LLM 调用失败时工作流停止并输出 Debug 信息。
- [ ] RAG Runner 检索失败时记录结构化错误信息。
- [ ] 在 `fire` 环境下完整跑通已确认的 W-S1/W-S2 各一份文件，每份生成三类问题各 1 条。
- [ ] 首个真实 Run 登记为 baseline，报告明确 `judge_calibrated=false`，不输出方向性比较结论。
