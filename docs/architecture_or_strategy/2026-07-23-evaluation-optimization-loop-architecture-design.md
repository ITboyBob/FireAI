# 分卷一：评测执行与报告架构

> **卷册角色**：新评测系统的运行编排、run 状态与双报告写出分卷
>
> **最后更新**：2026-07-29
>
> **当前状态**：架构已收敛为 evaluation-only，代码尚未实现

## 0. 卷册导航与本卷边界

| 卷册 | 文档 | 负责内容 |
| --- | --- | --- |
| 总卷 | [新评测系统设计总卷](../../新评测系统设计总卷.md) | evaluation 范围、八个维度、读取顺序和跨卷规则 |
| 分卷一（本文） | `2026-07-23-evaluation-optimization-loop-architecture-design.md` | 运行被测 RAG、保存逐 case 观测、调用评分与聚合、维护 run 状态、直接写出两份报告 |
| 分卷二 | [val_set 生成与冻结](./2026-07-27-ragas-val-set-query-generation-design.md) | 冻结 chunks 到正式 `val_set.json` 的生成、人工核验与发布 |
| 分卷三 | [Metric 与评分契约](./2026-07-27-ragas-response-reference-rubric-judge-design.md) | `metrics.json`、八项 Metric、统一结果、聚合算法与单项错误语义 |

本文只回答以下问题：

- 何时读取正式 `val_set.json` 与 `metrics.json`。
- 怎样在不改变被测 RAG 行为的前提下运行每个 case 并保存观测。
- 何时调用分卷三定义的评分与聚合。
- 怎样维护 run 状态。
- 怎样让两个 writer 读取同一个不可变聚合结果并分别直接写出 JSON 和 Markdown。

本文不定义 `val_set.json` 或 `metrics.json` 字段，不复述 Metric 公式、rubric、结果字段、聚合数学或单项错误字段。

## 1. 架构结论

新评测系统采用一次性离线运行流程：

```text
正式 val_set.json + 正式 metrics.json
  -> PreflightValidator
  -> EvaluationRunner
  -> RagExecutionAdapter
  -> CaseObservationRecorder -> CaseObservation（实际 Query、最终有序 chunks 与回答）
  -> MetricDispatcher
  -> ResultAggregator
  -> 不可变 AggregatedEvaluationResult
  -> JsonReportWriter -> report.json
  -> MarkdownReportWriter -> report.md
```

两个 writer 接收同一个 `AggregatedEvaluationResult` 实例。`MarkdownReportWriter` 直接把该对象组织成 Markdown 文本，不读取 `report.json`，也不调用 Streamlit、Rich、Dashboard 或旧评测报告代码。

现有 RAG 是被测对象。运行适配层只传入 Query、观察检索过程并取得回答，不改变检索深度、召回、融合、排序、提示词或回答生成行为。

## 2. 输入、输出与所有权

### 2.1 正式输入

一次 run 只接受两份已经冻结的数据文件：

- 正式 `val_set.json`：由分卷二定义、人工核验并发布。
- 正式 `metrics.json`：由分卷三定义并发布。

评测发起方还必须在评测前显式提供 `system_snapshot`。它是本次 run 的启动上下文，不是第三份冻结数据文件；运行器只校验四个固定字段、复制并冻结，不从代码、环境变量或运行结果猜测字段值。

运行开始后，两份正式输入与 `system_snapshot` 在本次 run 内保持不变。分卷一保存两份文件的稳定身份引用和快照副本，使报告能追溯到本次实际读取的输入与被测系统配置，但不在本文复制两份文件的 schema。

### 2.2 运行输出

每次 run 使用独立目录：

```text
reports/evaluation_baseline/<run_id>/
  report.json
  report.md
```

- `report.json` 是机器可读输出。
- `report.md` 是人类可读输出。
- 两份文件并列产生，不存在 JSON 到 Markdown 的下游转换。
- 两份文件都来自同一个已冻结的 `AggregatedEvaluationResult`。
- run 为 `incomplete` 时仍写出两份文件，保留已完成结果和错误证据。

本文拥有报告目录、写出时机和 run 级状态；分卷三拥有逐 Metric 结果与汇总结果的内部契约。

## 3. Preflight

`PreflightValidator` 在创建正式 run 之前完成以下检查：

1. 确认 `val_set.json` 和 `metrics.json` 均存在且可读。
2. 分别调用分卷二和分卷三提供的契约校验器，不在运行层重写校验规则。
3. 确认 Metric 集合与总卷列出的八个维度一致。
4. 确认每个 case 能提供分卷三声明的评分输入。
5. 确认被测 RAG 的运行入口与所需索引可用。
6. 确认评测发起方显式提供的 `system_snapshot` 恰好包含四个固定字段；字段值均可为 `null`，但不得包含 API Key。
7. 确认目标 `run_id` 不会覆盖已有报告目录。

只有 preflight 全部通过才创建正式 run 并进入 `running`。未通过的输入不进入 run 生命周期，也不产生看似完成的 baseline 报告。

## 4. 逐 case 执行流程

`EvaluationRunner` 按冻结 `val_set` 的 case 顺序执行，每个 case 完成以下动作：

1. 从冻结 case 读取 Query 及其评测引用。
2. 通过 `RagExecutionAdapter` 调用当前被测 RAG。
3. 保存本次实际返回的最终融合后有序 chunks；每项只表达稳定 `chunk_id` 与本次实际使用的完整 `text`，数组顺序就是唯一 rank。
4. 保存被测 RAG 的最终回答。
5. 把完整 `CaseObservation` 交给 `MetricDispatcher`。
6. 调用分卷三定义的八项 Metric，并保存其返回结果。
7. 即使某一项 Metric 返回错误，也继续调用本 case 其余 Metric，并继续运行后续 case。

评测适配层不得为了补齐观测而再次检索、静默去重、重新排序、补写回答或改变被测 RAG 的输入。缺失或非法观测如何形成单项结果，由分卷三解释；分卷一只执行“继续运行并保留返回结果”。

## 5. 逐 case 观测边界

`CaseObservationRecorder` 保存的 `CaseObservation` 只包含本次实际运行发生的以下事实：

- 本次使用的 Query 快照。
- 最终融合后有序 chunks 中每项稳定 `chunk_id` 与本次实际使用的完整 `text`；数组顺序就是唯一 rank。
- 被测 RAG 生成的最终回答。

Recorder 不补造、去重或重排最终列表，也不把未实际返回的数据写入持久化观测。

冻结参考答案和相关集合由分卷二提供；Metric 读取哪些观测、怎样解释空值以及怎样生成结果由分卷三决定。本文不建立第二份评分输入表。

## 6. 组件职责

| 组件 | 执行动作 | 明确不做 |
| --- | --- | --- |
| `PreflightValidator` | 调用上游校验器，检查运行入口与输出目标 | 不重写上游 schema |
| `EvaluationRunner` | 排列 case 执行、评分、聚合和写出顺序 | 不计算任何 Metric |
| `RagExecutionAdapter` | 用 Query 调用当前 RAG，暴露最终融合后有序 chunks 与回答 | 不改变被测 RAG 行为 |
| `CaseObservationRecorder` | 保存实际 Query、最终有序 chunks 的稳定 `chunk_id` 与完整 `text`，以及本次回答 | 不补造、去重或重排最终列表 |
| `MetricDispatcher` | 按分卷三配置调用八项 Metric，并收集全部返回结果 | 不解释公式或错误字段，不向生成端 Metric 传入 chunks |
| `ResultAggregator` | 在全部 case 执行后调用分卷三定义的聚合算法 | 不另写聚合规则 |
| `AggregatedEvaluationResultBuilder` | 合并 run 上下文与分卷三返回的 case、汇总结果，冻结最终对象 | 不重新计算分数 |
| `JsonReportWriter` | 直接从最终对象写出 JSON | 不生成 Markdown |
| `MarkdownReportWriter` | 直接从最终对象生成并写出 Markdown | 不读取 JSON，不调用展示框架 |

组件依赖方向固定为运行编排调用适配器、Recorder 和评分组件；评分组件返回结果后，运行编排再调用聚合与 writer。任何 writer 都不得反向调用 RAG、Metric 或另一个 writer。

## 7. Metric 调度与聚合调用

`MetricDispatcher` 读取正式 `metrics.json`，为每个 case 调用分卷三登记的八项实现。所有需要检索输出的 Metric 只从冻结 case 与本次 `CaseObservation` 消费最终融合后有序 chunks；生成端 Metric 不消费 chunks。Dispatcher 不在运行层改变参数或补充评分规则。

全部 case 的八项调用结束后，`EvaluationRunner` 只调用一次 `ResultAggregator`。`ResultAggregator` 严格执行分卷三的聚合契约并返回汇总结果；分卷一不计算均值、不筛除错误 case，也不定义空值传播。

单项 Metric 返回错误时执行路径固定为：

```text
保存该项返回结果
  -> 继续本 case 的其余 Metric
  -> 继续后续 case
  -> 调用统一聚合
  -> run 标记为 incomplete
  -> 仍写出 report.json 与 report.md
```

单项 Metric 错误的 run 级处理只有上述路径。

## 8. Run 状态

正式 run 只使用三个状态：

| 状态 | 进入条件 | 离开条件 |
| --- | --- | --- |
| `running` | preflight 通过并创建正式 run | 全部 case、聚合和两份报告写出结束 |
| `completed` | 所有 Metric 均完成，且两份报告已经写出 | 终态 |
| `incomplete` | 至少一项 Metric 返回错误，运行继续完成聚合并写出两份报告 | 终态 |

状态转换固定为：

```text
preflight 通过 -> running -> completed
                         \-> incomplete
```

`incomplete` 表示本次运行已经完成所有步骤，但含有单项 Metric 错误。两份报告必须存在，并明确呈现同一个 run 状态。

## 9. 不可变聚合结果

`AggregatedEvaluationResultBuilder` 在统一聚合完成后一次性建立最终对象。该对象组合：

- 本次 run 的稳定身份和状态。
- 本次实际读取的冻结输入身份。
- 每个 case 的运行观测与分卷三返回结果。
- 分卷三返回的八项汇总结果。

顶层字段固定为：

| 字段 | 契约 |
| --- | --- |
| `schema_version` | 本报告对象的 schema 版本 |
| `report_type` | 固定为 `baseline` |
| `run_id` | 本次评测的稳定身份 |
| `created_at` | 本次对象冻结时间 |
| `status` | 仅 `completed` 或 `incomplete` |
| `system_snapshot` | 评测发起方在评测前显式提供、经运行器校验和冻结的被测系统快照 |
| `val_set` | 正式 `val_set.json` 的 `val_set_id` 与 `content_hash` 引用 |
| `metrics_config` | 正式 `metrics.json` 的 schema 版本与配置 hash 引用 |
| `cases` | 全部逐 case 观测及其八项 `MetricResult`，嵌套结构由下表固定 |
| `metric_summaries` | 分卷三返回的八项 `MetricSummary` |

`system_snapshot` 内部字段固定为：

| 字段 | 契约 |
| --- | --- |
| `retrieval_algorithm` | 检索算法；允许 `null` |
| `reranker_algorithm` | Reranker 算法；允许 `null` |
| `answer_model_id` | 回答模型 ID；允许 `null` |
| `answer_prompt` | 输入回答模型的 Prompt 全文；允许 `null` |

四个字段都由评测发起方在评测前显式写入。运行器只校验字段集合和值类型、复制并冻结；不得从代码、环境变量或运行结果猜测，也不得在该对象中保存 API Key。回答模型字段仅有 `answer_model_id`，不得另设兼容别名。

`cases` 的嵌套结构固定为：

| 路径 | 契约 |
| --- | --- |
| `cases[]` | 每项恰好包含 `case_id`、`observation`、`metric_results` |
| `cases[].case_id` | 本 case 的稳定身份 |
| `cases[].observation` | 恰好包含 `query`、`final_retrieved_chunks`、`answer` |
| `cases[].observation.query` | 本次实际提交给被测 RAG 的 Query |
| `cases[].observation.final_retrieved_chunks` | 本次实际返回的最终融合后有序 chunk 数组；数组顺序就是唯一 rank |
| `cases[].observation.final_retrieved_chunks[]` | 每项恰好包含 `chunk_id` 与完整 `text` |
| `cases[].observation.answer` | 被测 RAG 本次实际生成的回答 |
| `cases[].metric_results` | 必须恰好包含八项 `MetricResult`；每项 `MetricResult.case_id` 必须等于父级 `cases[].case_id` |

`MetricResult` 的其他内部字段由分卷三独占定义，本文不重复。Recorder 与 Builder 对 `observation` 只复制本次实际运行事实，不补造、去重或重排。

对象建立后不得由 writer 修改。两个 writer 在同一对象快照上分别工作，从而让 JSON 与 Markdown 表达同一次运行，而不让其中一个文件成为另一个文件的输入。

对象中 Metric 结果与汇总的具体字段仍以分卷三为唯一来源；本文只规定怎样把其返回值接入 run 并传给 writer。

## 10. 双报告直接写出

写出顺序由 `EvaluationRunner` 控制：

1. 完成全部 case 的 Metric 调用。
2. 调用分卷三的统一聚合。
3. 确定 `completed` 或 `incomplete`。
4. 建立并冻结一个 `AggregatedEvaluationResult`。
5. 把同一个对象交给 `JsonReportWriter`，直接写出 `report.json`。
6. 把同一个对象交给 `MarkdownReportWriter`，直接写出 `report.md`。

`MarkdownReportWriter` 负责把对象中的 run 概况、逐 case 结果、八项汇总和错误证据组织成 Markdown 文件。两个 writer 都只输出最终融合后有序 chunks 的稳定 `chunk_id` 与完整 `text`。Markdown writer 不解析 JSON，也不依赖模板页面、Dashboard、Streamlit、Rich 或旧报告工具。

两份 writer 的一致性验证比较同一对象投影出的 run 身份、输入身份、case 集合、Metric 结果、汇总结果和 run 状态。验证目标是确认两种表达来自同一对象，不是让 Markdown 反向解析 JSON。

## 11. 与旧评测系统的隔离

新评测运行代码不得导入或调用旧 Word/W RAG 评测系统的以下能力：

- Dataset 或 Query 生成代码。
- Metric、阈值、聚合或错误模型。
- 报告 schema、报告生成器或报告目录发现逻辑。
- Dashboard、Streamlit、Rich 或页面展示代码。

允许调用的是当前在线 RAG 的真实检索与回答能力，因为它是本次评测对象。适配器必须把“调用被测系统”和“复用旧评测实现”区分开。

## 12. 可直接转为实施计划的工作顺序

1. 接入分卷二的正式 `val_set.json` 校验器和稳定身份。
2. 接入分卷三的正式 `metrics.json` 校验器、八项实现和统一结果。
3. 实现 `RagExecutionAdapter`，只暴露本次实际返回的最终融合后有序 chunks 与回答。
4. 实现 `CaseObservationRecorder`，验证它保存实际 Query、最终有序 chunks 与回答，且不改变被测 RAG 输出。
5. 实现 `MetricDispatcher`，覆盖八项均被调用、检索端只消费最终有序 chunks、生成端不消费 chunks，以及单项错误后继续执行。
6. 实现 `ResultAggregator` 适配层，只调用分卷三算法。
7. 实现 run 状态转换和不可变 `AggregatedEvaluationResult` 构建。
8. 实现两个彼此独立的 writer，并写入同一 run 目录。
9. 验证 `completed` 与 `incomplete` 两条终态路径。
10. 使用冻结输入运行真实被测 RAG，完成首个 baseline 端到端验收。

实施计划不得在上述任务中重新发明 `val_set`、Metric 或聚合字段；发现缺口时回到对应分卷补齐后再继续。

## 13. 验收检查

- preflight 只调用分卷二、分卷三的正式校验规则。
- preflight 校验评测发起方显式提供的 `system_snapshot` 四字段，允许字段值为 `null`，不猜测字段值且不保存 API Key。
- 每个冻结 case 只运行一次当前被测 RAG。
- Recorder 只保存实际 Query、最终融合后有序 chunks 的稳定 `chunk_id` 与完整 `text`，以及最终回答；数组顺序就是唯一 rank，不补造、去重或重排。
- 所有需要检索输出的 Metric 只消费最终融合后有序 chunks；生成端 Metric 不消费 chunks。
- `cases[]` 每项恰好包含 `case_id`、`observation`、`metric_results`，其中 `observation` 使用本文固定结构，`metric_results` 恰好八项且每项 `case_id` 与父 case 一致。
- 每个 case 调用分卷三登记的全部八项 Metric。
- 任一单项 Metric 错误后，其余 Metric 和后续 case 继续执行。
- 聚合只在全部 case 执行结束后调用，并且只执行分卷三的算法。
- 无单项错误时 run 终态为 `completed`。
- 存在单项错误时 run 终态为 `incomplete`，两份报告仍然存在。
- 两个 writer 接收同一个不可变 `AggregatedEvaluationResult`。
- `report.md` 直接生成，不读取 `report.json`。
- 新评测运行代码不依赖 Streamlit、Rich、Dashboard 或旧报告模块。
- 真实 RAG 与真实 Judge 的端到端结果有独立验收证据，不能用文档或局部导入测试替代。

## 14. 当前实现状态

| 能力 | 状态 |
| --- | --- |
| evaluation-only 执行流程 | 设计已确认，尚未实现 |
| 正式输入 preflight | 设计已确认，尚未实现 |
| 被测 RAG 适配与逐 case 观测 | 设计已确认，尚未实现 |
| 八项 Metric 调度与统一聚合接入 | 设计已确认，尚未实现 |
| `completed` / `incomplete` run 状态 | 设计已确认，尚未实现 |
| JSON 与 Markdown 从同一对象直接写出 | 设计已确认，尚未实现 |
| 真实模型与新评测系统端到端 baseline | 尚未验证 |

本卷不记录依赖安装日志、测试计数或临时 smoke 结果。实现状态只能由当前代码和真实验收证据更新。
