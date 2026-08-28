# 新评测系统规范依赖审查架构设计

> **文档类型**：Architecture Design
>
> **日期**：2026-08-27
>
> **版本**：v1.0
>
> **状态**：Under Review / Blocked by BOB-55
>
> **关联需求**：Linear BOB-56「更新整体评测系统规范」；上游阻塞项 BOB-55「确定评测数据集规范」

---

## 1. 决策结论

### 1.1 当前选择

现有评测系统规范**不能按“格式、方法与指标均已确认无误”验收**。已确认正式数据文件组织采用“三类 JSONL + manifest”，且现有七项 Metric 的适用边界仅为 Golden Set；在 BOB-55 冻结三类 case 的评测语义和机器 schema 前，BOB-56 只确认已成立的算法条件、独立决策项及跨模块解决顺序，不进入代码实施。

### 1.2 决策理由

- `eval_set/` 当前只有 Golden Set 原始 QA、Adversarial Case 生成输出和 Edge Case 分类/生成素材，没有三类 case 共用的正式评测 schema。
- 现有 Golden Set 虽有 `qa_id`，但没有正式 `case_id` 映射契约、完整相关 chunk 集 (C_q) 或 case 类型；Adversarial / Edge 产物也没有统一映射到评分输入。
- Precision、Recall、AP/MAP 与 MRR 只有在 (C_q) 是完整相关集合时才可解释；当前数据没有提供该前提。
- 现有七项 Metric 只用于 Golden Set。Adversarial Case 与 Edge Case 分别需要其目标明确后再补充额外 Metric，才能执行各自评测；其中 Golden Set 同时是 Adversarial Case 的生成种子。
- Adversarial Case 的“检索鲁棒性”与“安全处置”是两种不同目标，不能默认共用同一参考答案或额外 Metric。

### 1.3 当前实现状态

现有总卷和两份分卷尚无对应的新评测系统代码、正式 `metrics.json`、正式评测 case 文件或端到端 baseline。当前依赖版本与目标公开接口可以在 `fire` 环境中定位，但这只证明依赖契约可核验，不代表数据输入、Metric 适用性或整体方法已经验收。

## 2. 背景与目标

### 2.1 当前状态

| 领域 | 当前权威描述 | 当前事实 | BOB-56 判断 |
| --- | --- | --- | --- |
| Golden Set | `eval_set/RAG_Golden_Set.json` | 顶层 `records`；每条只有 `qa_id`、`question`、`answer`、`legal_basis`、`missing_fields` | 是七项 Metric 的唯一适用数据类别，也是 Adversarial Case 的生成种子；正式执行仍须由 BOB-55 补齐必要评分输入 |
| Adversarial Case | `eval_set/Adversarial_Case_Prompt.md` | 输出改写可行性、改写 Query 与生成验证；明确不生成系统期待行为 | 生成产物不能直接决定安全 Metric 或拒答期望 |
| Edge Case | `eval_set/Edge_Case生成设计方案.md` | 只固定五个二级 Bucket 与本地 chunk 作为生成 `context` | 尚无正式输出 schema、参考答案、(C_q) 或期待行为 |
| 评测方法 | 分卷一 | 定义 preflight、运行、观测、Metric 调度、聚合和报告 | 方法顺序成立，但其输入门禁依赖 BOB-55 |
| 评测指标 | 分卷三 | 固定七项 Metric 及统一结果/聚合 | 公式与 SDK 映射可局部确认；七项仅适用于 Golden Set，Adversarial / Edge 的额外指标尚待定义 |

另有一处必须由 BOB-55 消除的直接冲突：`Adversarial_Case生成流程.md` 的流程概览包含“确定系统期待行为”，但其具体实现 `Adversarial_Case_Prompt.md` 明确规定“不生成系统期待行为”。在两者统一前，下游不能猜测 Adversarial Case 应当正常作答、拒答还是输出其他安全响应。

### 2.2 核心目标

1. 区分数据集、评测方法、评测指标各自可以独立决策的问题。
2. 标出必须先由 BOB-55 冻结、再由 BOB-56 收口的相互依赖问题。
3. 证明每个 Metric 所需输入都能由正式 case 或运行时观测唯一提供。
4. 让 Golden Set 的七项结果与 Adversarial / Edge 后续新增指标的结果保持可追溯，不混淆不同评测目标。
5. 在代码实施前形成可由 schema 校验器和契约测试机械验证的闭环。

### 2.3 问题分类

| 类型 | 问题 | 为什么属于该类型 | 处理方式 |
| --- | --- | --- | --- |
| 已确认独立问题 | 正式文件采用三类 JSONL + manifest | 物理容器不改变 QA 语义；已确认其机器流式读取、逐条 diff、分类型生成/审核与发布追溯优势 | BOB-55 据此冻结正式 schema；本轮不创建数据文件 |
| 独立问题 | 已固定依赖版本的公开接口是否存在 | 可在 `fire` 环境独立核验，不依赖正式 case 内容 | 继续保留 import 与真实调用两级验收；不把 import 当端到端完成 |
| 相互依赖 | 三类 case 的评测目标、期待行为和正式字段 | 先知道要测正常回答、检索鲁棒性、拒答、澄清还是安全处置，才能确定字段 | 按 §6 步骤 1–2 解决 |
| 相互依赖 | (C_q) 语义与 Precision / Recall / AP / MRR | 是否为“完整相关集合”直接改变这些公式的分母和可解释性 | 按 §6 步骤 3–4 解决 |
| 相互依赖 | reference 语义与 Ragas Metric | 相同文本在普通 QA、恶意 Query 和不可回答 Query 下可能代表不同目标 | 按 §6 步骤 1、3、4 解决 |
| 相互依赖 | Adversarial / Edge 期待行为与额外 Metric | 未先定义期待行为，就无法定义其独立于 Golden Set 七项之外的评测指标 | 按 §6 步骤 1、4 解决 |

### 2.4 关键约束

#### 硬约束

- 评测数据分 Golden Set、Adversarial Case、Edge Case 三类，但不要求覆盖消防法律领域全部场景。
- 数据文件必须机器友好，字段类型、必填条件、枚举和版本可机械校验。
- (R_q) 只来自被测 RAG 本次实际返回的最终融合后有序 Top-5；不得读取融合前旁路。
- (G_q) 只由本次 run 的不可变系统 snapshot 标识。
- 需要 (C_q) 的 Metric 只能消费人工确认的完整相关 chunk 集；生成候选或单个来源 chunk 不能自动视为完整集合。
- 现有七项 Metric 不得被用于 Adversarial 或 Edge；这两类 case 在额外指标定义前不得进入其正式评测。

#### 环境约束

- 所有 Python 与测试在 conda 环境 `fire` 中执行。
- pytest、CI 或默认配置验证在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。
- 当前被测 RAG 没有独立的恶意意图安全处置输出字段；其结构化输出是 `conclusion`、`citations`、`scope`、`uncertainty` 和 `evidence`。

#### 性能约束

- 第一阶段为离线 baseline，不以在线延迟为验收目标。
- Judge 型 Metric 的调用次数必须能由 Golden Set case 数、已定义的额外 Metric 与 (R_q) 长度预先计算，避免产生无意义的外部调用。

## 3. 单一事实来源（SoT）

| 项目 | 值 |
| --- | --- |
| SoT artifact | `docs/architecture_or_strategy/2026-08-27-evaluation-system-specification-dependency-review.md` |
| SoT type | other：BOB-56 审查结论与决策状态 |
| Last verified | 2026-08-27 |

**冲突规则**：当总卷、分卷、CODEMAP 或后续实施计划对“BOB-56 是否已可验收、哪些问题独立、哪些问题互相依赖、应按什么顺序解决”与本文冲突时，以本文为准并先修订冲突文档。本文不替代 BOB-55 对正式数据集 schema 的最终决策，也不替代分卷一和分卷三在各自已成立范围内的字段与算法所有权。

**范围**：本文只治理 BOB-56 的审查状态、问题分类、依赖顺序、候选方案和验收门禁。正式评测数据 schema 在 BOB-55 决策后由 `eval_set/` 发布；运行编排与评分实现仍分别由分卷一、分卷三定义。

## 4. 环境基线

| 检查项 | 结果 |
| --- | --- |
| OS | macOS 26.5.2（Build 25F84） |
| Python | conda `fire`：Python 3.14.2 |
| 依赖 | DeepEval 4.1.4、Ragas 0.4.3、TruLens Core/Feedback 2.9.0 |
| 当前正式 chunks | 856 条；仅为 2026-08-27 易变快照，不进入永久常量 |
| 新评测实现 | 尚无正式 `metrics.json`、正式 case 文件、运行代码或真实 baseline |

## 5. 已确认方案与待决策事项

### 5.1 正式数据文件组织

#### 已确认方案：三类 JSONL + manifest

```text
manifest.json
golden.jsonl
adversarial.jsonl
edge.jsonl
```

| 已确认理由 | 实施约束 | 与目标架构关系 |
| --- | --- | --- |
| 每行一个 case，机器流式读取和逐条 diff 友好；三类数据可独立生成/审核；manifest 可冻结 schema、文件 hash 与数量 | 发布时必须校验 manifest 与三份文件的一致性；单行对象可读性略低 | 最符合三类数据独立生成、统一 preflight 和发布追溯的目标 |

## 6. 待完成工作

| 步骤 | 组件 | 依赖关系 | 完成判据 |
| --- | --- | --- | --- |
| 1 | 三类 case 的评测目标 | BOB-55 | 明确 Golden、Adversarial、Edge 各自期待系统回答、拒答、澄清还是安全处置 |
| 2 | 正式数据集 schema 与文件组织 | 依赖步骤 1；文件组织已确认采用三类 JSONL + manifest | 每项条件必填字段可机械校验；未生成的候选不进入正式 case |
| 3 | Golden Set 的 (C_q) 与参考答案构建/人工确认 | 依赖步骤 1–2 | 每个需要检索 Metric 的 Golden Set case 有完整 (C_q)；每个需要 reference Judge 的 Golden Set case 有与目标一致的参考输出 |
| 4 | Adversarial / Edge 额外 Metric 定义 | 依赖步骤 1–3 | 额外 Metric 的业务含义、输入来源和计算方法成立 |
| 5 | `metrics.json`、preflight 与聚合契约 | 依赖步骤 2–4 | 配置和运行契约只调用 Golden Set 七项，以及已定义的 Adversarial / Edge 额外指标 |
| 6 | Runner 与报告实现 | 依赖步骤 5 | 保留统一 run 生命周期，并输出与各类评测目标一致的结果 |
| 7 | 契约和真实调用验收 | 依赖步骤 6 | fixture、错误路径和真实 Judge/RAG baseline 均有证据 |

步骤 1–4 是 BOB-55 与 BOB-56 的强依赖链，不能交换为“先实现 runner，再补字段”。步骤 5–7 才属于可执行实施阶段。

## 7. 关键风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 把生成 `context` 或来源 chunk 直接当完整 (C_q) | Recall、AP/MAP 和 MRR 的分母错误 | 正式 case 发布前由人工确认完整相关集合，并记录确认状态 |
| 用原 Golden answer 作为恶意问题的安全参考答案 | 回答违法目的可能被 Ragas 判高分 | 先决策 Adversarial 是“检索鲁棒性”还是“安全处置”，两者不得混为一个 objective |
| 将 Golden Set 七项用于 Edge 或 Adversarial | 评测结果与不可回答或安全目标不一致 | 先完成各自额外 Metric 定义；在此之前不执行该类正式评测 |
| 将 LLM Judge 的 reason 当法规证据 | 报告形成虚假可核验证据 | reason 只作诊断解释，法规正确性必须由 reference/chunk ground truth 支撑 |
| 混合不同目标的 Metric 结果 | 结论失真且不同版本不可比 | Golden Set 七项与 Adversarial / Edge 额外指标分别记录，待后续方法契约定义可比口径 |

## 8. 已确认与待决策事项

| 决策 ID | 状态 | 建议 | 用户需要确认什么 |
| --- | --- | --- | --- |
| D2 | 已确认 | 采用三类 JSONL + manifest | 无；BOB-55 据此冻结正式 schema，但本轮不创建实际数据文件 |
| D6 | 已确认 | 继续使用分卷一的单一 run 生命周期和实际 (R_q) 观测边界 | 无；但实现必须等待 D1 与 BOB-55 |
| D7 | 已确认 | Precision、Recall、AP/MAP、MRR 的公式只在完整 (C_q) 条件下成立 | 无；BOB-55 必须为 Golden Set 提供该条件 |
| D1 | 待决策 | 采用“检索鲁棒性”和“安全处置”两个不同 Adversarial objective；首期只选一个进入正式集 | Adversarial Case 首期究竟测哪一个目标 |

## 附录 A：评分输入最小语义契约

下表定义的是 BOB-55 必须覆盖的**语义输入**，不是替 BOB-55 冻结最终字段名。

| 语义输入 | 生产方 | 消费方 | 必填条件 | Source |
| --- | --- | --- | --- | --- |
| schema / dataset 版本 | 正式数据集 | preflight、报告追溯 | 全局必填 | This doc §2.2、§5.1 |
| 稳定 case 身份 | 正式数据集 | Runner、`MetricResult`、报告 | 每个正式 case 必填且全局唯一 | This doc §2.2、§6 |
| case 类型 | 正式数据集 | 数据类别追溯、报告解释 | 每个正式 case 必填；Golden / Adversarial / Edge | This doc §2.2、§6 |
| evaluation objective | 正式数据集 | Adversarial / Edge 的额外 Metric 与 reference 解释 | Adversarial 与 Edge 必填；Golden 可固定默认值 | This doc §6、§8 D1 |
| Query | 正式数据集 | 被测 RAG、全部 Query 相关 Metric | 每个正式 case 非空 | This doc §2.2、§6 |
| 参考输出 | 正式数据集 | Ragas reference-based Judge | 仅对启用该 Metric 的 case 必填，且必须与 objective 一致 | This doc §6、§7 |
| 完整相关 chunk 集 (C_q) | 正式数据集 | Golden Set 的 Precision、Recall、AP/MAP、MRR | 仅对 Golden Set 中启用这些检索 Metric 的 case 必填且非空 | This doc §1.2、§6 步骤 3、§8 D7 |
| 期待行为 | 正式数据集 | Adversarial / Edge 的后续额外 Metric | 由 BOB-55 和 D1 的评测目标决定 | This doc §6、§8 D1 |
| subtype / bucket | 正式数据集 | 分层分析 | Edge 必填；其他类型按决策可选 | This doc §2.1、§6 |
| 生成与人工审核追溯 | 正式数据集发布流程 | 审计、数据发布门禁 | 生成型 case 必填；未通过审核不得发布 | This doc §6、§7 |
| 最终 (R_q) | 本次被测 RAG 观测 | 检索端 Metric | 运行时产生，不得由数据集预填 | This doc §2.4、§7 |
| `answer_text` | 本次被测 RAG 观测 | DeepEval、Ragas、行为 Metric | 运行时产生且非空 | This doc §2.4、§6 |
| 不可变 (G_q) snapshot | preflight | corpus 一致性 | 每个 run 建立一次 | This doc §2.4 |

## 附录 B：现有七项 Metric 审查

| Metric | 数学/API 定义 | 跨三类数据适用性 | 当前结论 | Source |
| --- | --- | --- | --- | --- |
| Precision | 公式成立 | 仅 Golden Set；依赖完整 (C_q) | 条件确认 | This doc §1.2、§6 步骤 3、§8 D7 |
| Recall | 公式成立 | 仅 Golden Set；依赖非空完整 (C_q) | 条件确认 | This doc §1.2、§6 步骤 3、§8 D7 |
| TruLens Context Relevance | 可按 Query + (R_q) 逐 chunk 评分 | 仅 Golden Set；不等价于 ground-truth retrieval correctness | 保留候选，限定解释 | This doc §7 |
| MAP@5 | 单 case 应称 AP@5，跨 case 才是 MAP@5 | 仅 Golden Set；依赖完整 (C_q) 和稳定 rank | 条件确认 | This doc §1.2、§6 步骤 3、§8 D7 |
| MRR@5 | 公式成立 | 仅 Golden Set；依赖至少一个可定义的相关 chunk；只关注首个命中 | 条件确认 | This doc §1.2、§6 步骤 3、§8 D7 |
| DeepEval Answer Relevancy | SDK 映射可核验 | 仅 Golden Set；只测回答是否回应 Query，不证明法规正确或安全 | 保留候选，限定解释 | This doc §7 |
| Ragas RubricsScoreWithReference | reference-based 1–5 分及归一化可核验 | 仅 Golden Set；只有 reference 与其评测目标一致时成立 | 条件确认 | This doc §6、§7 |

## 附录 C：BOB-56 验收门禁

| 门禁 | 通过条件 | Source |
| --- | --- | --- |
| 数据格式 | manifest 与三类 JSONL 可解析、版本化、hash、逐 case schema 校验；三类 case 的条件字段不含歧义 | This doc §5.1、附录 A |
| 方法输入闭包 | 每个 Metric 输入都有唯一生产方；无字段名猜测或运行时补造 ground truth | This doc §6、附录 A |
| Metric 语义 | 七项 Metric 仅对 Golden Set 的业务含义成立；Adversarial / Edge 已定义各自额外 Metric 后才可进入评测 | This doc §1.2、附录 B |
| 结果解释 | Golden Set 七项与 Adversarial / Edge 额外 Metric 的结果不混淆；可比口径由后续方法契约定义 | This doc §6、§7 |
| 错误边界 | preflight、Metric error、run fatal 与 dataset publication failure 各归其所有者 | This doc §6、§7 |
| 真实验收 | 契约 fixture、边界样本、真实 RAG 与真实 Judge 均通过；仅文档和 import smoke 不算完成 | This doc §6 |
