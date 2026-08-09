# 分卷一：评测执行与报告架构

> **卷册角色**：新评测系统的运行编排、run 状态与双报告写出分卷
>
> **最后更新**：2026-08-09
>
> **当前状态**：架构已收敛为 evaluation-only，代码尚未实现

## 0. 卷册导航与本卷边界

| 卷册 | 文档 | 负责内容 |
| --- | --- | --- |
| 总卷 | [新评测系统设计总卷](../../新评测系统设计总卷.md) | evaluation 范围、八个维度、读取顺序和跨卷规则 |
| 分卷一（本文） | `2026-07-23-evaluation-optimization-loop-architecture-design.md` | 运行被测 RAG、保存逐 case 观测、调用评分与聚合、维护 run 状态、直接写出两份报告 |
| 分卷二 | [val_set 生成与冻结](./2026-07-27-ragas-val-set-query-generation-design.md) | 当前仓库全部 chunks 到正式 `val_set.json` 的纯脚本生成、校验与发布 |
| 分卷三 | [Metric 与评分契约](./2026-07-27-ragas-response-reference-rubric-judge-design.md) | `metrics.json`、八项 Metric、统一结果、聚合算法、稳定错误码与未决错误边界 |

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

第一阶段的一次 run 只接受两份已经冻结的数据文件：

- 正式 `val_set.json`：由分卷二定义，经纯脚本生成、校验并发布。
- 正式 `metrics.json`：由分卷三定义并发布。

运行开始后，两份正式输入在本次 run 内保持不变。分卷一保存两份文件的稳定身份引用和快照副本，使报告能追溯到本次实际读取的输入，但不在本文复制两份文件的 schema。

`system_snapshot.json` 不是第一阶段输入，不进入第一阶段执行计划、preflight、运行步骤或报告构建。只在评测数据集生成完成后进入后续阶段；以下契约用于届时实现，不得借此把它提前加入第一阶段。

#### 2.1.1 后续 `system_snapshot.json` 契约

`system_snapshot.json` 是独立、机器可校验的被测系统快照，顶层按三个业务域组织：

| 顶层域 | 后续阶段契约 |
| --- | --- |
| `retrieval_pipeline` | 有序数组，保存关键词检索、向量检索和加权融合的实际顺序与配置 |
| `chunking` | 保存当前法规条文切分规则及稳定 `chunk_id` 形态 |
| `indexed_documents` | 对象；保存当次快照的原始源文档名、文档/chunk 计数与 \(C_q\) 内容 hash |

`retrieval_pipeline` 必须投影当前代码的三个有序阶段：

1. SQLite FTS5 BM25 关键词检索：使用 trigram tokenizer；查询发生 `OperationalError` 或无命中时回退到 LIKE；候选上限为 `max(top_k * 3, top_k)`。
2. SentenceTransformer 向量检索：对规范化后的查询文本编码，再对查询向量归一化，使用 FAISS `IndexFlatIP` 检索；候选上限同样为 `max(top_k * 3, top_k)`。快照从实际运行配置记录 embedding 模型、device、batch size 和 max sequence length；截至 2026-08-09 当前环境核验值分别为 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`、`cpu`、`32`、`null`，该当前值会随环境变更，不得作为永久常量。
3. 加权融合：关键词与向量分数分别归一化，按 `keyword_weight=0.6`、`vector_weight=0.4` 计算融合分；依次按 combined score、keyword score、vector score 降序，再按 `chunk_id` 升序，最终 `top_k=5`。

查询规范化是整条检索管线的前置行为，可随管线快照记录，但不得冒充第四种检索算法。

`chunking` 必须投影当前规则：按法规条文切分，`max_chunk_chars=300`；只有条文包含多个段落且全文超过阈值时，才按段落累积切分；不拆分单个段落，不使用 overlap。`chunk_id` 形式为 `<document_id>#article-<article_index>[-part-<chunk_index>]`。

`indexed_documents` 必须是对象，而非裸数组；其字段至少包含：

| 字段 | 契约 |
| --- | --- |
| `source_documents` | 原始源文档 basename 数组；每项必须是“题目 + 真实扩展名”，不得使用 chunk JSONL、`document_id`、路径或无扩展名标题 |
| `document_count` | 从当前索引映射机械统计的文档数 |
| `chunk_count` | 从当前索引映射机械统计的 chunk 数 |
| `cq_content_hash` | 分卷三定义的 \(C_q\) canonical JSON SHA-256 |

`source_documents[]` 记录当次快照的源文档 basename；即使后续该文档已不在仓库，快照仍保留当时名称。截至 2026-08-09，当前 `vector_map.json` 与 chunks 核验为 20 个文档、876 个 chunks；这只是易变的当前核验结果，实际快照必须重新机械计算。

下表是当前 20 个索引文档对应 `source_documents[]` 值的来源举证，不是快照的额外 schema 或排序契约：

| 核对来源 | `source_documents[]` 当前值 |
| --- | --- |
| `data/manifests/incremental_imports.json` 的 `source_path` basename | `中华人民共和国消防救援衔条例.docx` |
| 同上 | `安全生产行政执法与刑事司法衔接工作办法.doc` |
| 同上 | `河北省消防安全领域信用管理暂行细则.doc` |
| 同上 | `河北省消防技术服务监督管理规定.doc` |
| 同上 | `河北省消防行政执法裁量实施办法.doc` |
| 同上 | `河北省火灾事故调查处理规定.docx` |
| 同上 | `消防产品监督管理规定.doc` |
| 同上 | `消防监督检查规定.doc` |
| 同上 | `河北省消防设施管理规定.docx` |
| 同上 | `社会消防安全教育培训规定.doc` |
| 同上 | `河北省消防救援机构执法过错责任追究规定.doc` |
| 同上 | `河北省火灾高危单位消防安全管理规定.docx` |
| 同上 | `高层民用建筑消防消防安全管理规定.doc` |
| 同上 | `公共娱乐场所管理规定.docx` |
| `app/services/corpus_ingestor.py::KNOWN_DOCUMENT_IDS` 与 `法律文本/done` 文件名 | `消防法--2019年4月23日.doc` |
| 同上 | `河北省消防条例.docx` |
| 同上 | `河北省消防安全责任制实施办法.docx` |
| 同上 | `河北省消防安全责任制规定.docx` |
| 同上 | `消防安全责任制实施办法.doc` |
| 同上 | `机关、团体、企业、事业单位消防安全管理规定.doc` |

当 `system_snapshot.json` 在后续阶段进入运行与报告时，机器友好的 `report.json` 同时引用 `system_snapshot.indexed_documents.source_documents` 与 `system_snapshot.indexed_documents.cq_content_hash`；人类友好的 `report.md` 只引用和展示 `source_documents`，不得展示 `cq_content_hash`。两份报告均不另建 \(C_q\) 文件清单或重复 hash 字段。

### 2.2 运行输出

`completed` 或 `incomplete` run 的最终目录为：

```text
reports/evaluation_baseline/<run_id>/
  run_status.json
  report.json
  report.md
```

- `report.json` 是机器可读输出。
- `report.md` 是人类可读输出。
- 两份文件并列产生，不存在 JSON 到 Markdown 的下游转换。
- 两份文件都来自同一个已冻结的 `AggregatedEvaluationResult`。
- run 为 `incomplete` 时仍写出两份文件，保留已完成结果和错误证据；`failed` 不发布最终双报告。
- `completed` 或 `incomplete` 的最终目录恰好包含 `run_status.json`、`report.json`、`report.md`；`failed` 的最终目录恰好只包含 `run_status.json`。隐藏 staging 使用同名 `run_status.json`，但不得被发现为正式 run。

本文拥有报告目录、写出时机和 run 级状态；分卷三拥有逐 Metric 结果与汇总结果的内部契约。

## 3. Preflight

`PreflightValidator` 在创建正式 run 之前完成以下检查：

1. 确认 `val_set.json` 和 `metrics.json` 均存在且可读。
2. 分别调用分卷二和分卷三提供的契约校验器，不在运行层重写校验规则。
3. 确认 Metric 集合与总卷列出的八个维度一致。
4. 确认每个 case 能提供分卷三声明的评分输入。
5. 确认被测 RAG 的运行入口与所需索引可用。
6. 确认目标 `run_id` 不会覆盖已有报告目录。

只有 preflight 全部通过才创建正式 run 并进入 `running`。Preflight 收集所有安全可评估错误：缺失的上游文件不再解析、不能成立的配置不再检查依赖它的 case、不可用的 RAG 入口不再检查索引，`run_id` 冲突独立检查；它不调用真实 RAG、Judge 或 Metric。未通过的输入不进入 run 生命周期，也不产生看似完成的 baseline 报告。未通过条件的稳定错误码、稳定顺序和选择优先级由[分卷三第 9 节](./2026-07-27-ragas-response-reference-rubric-judge-design.md#9-稳定错误码与处理责任)统一定义，本卷不复制值域。

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

调用被测 RAG 失败、无法取得完整 Query/最终 chunks/回答，或 Recorder 无法验证、冻结或保存观测，均是 run 级 fatal：立即进入 `failed`，不调用后续 Metric、case、聚合或 writer，不补造观测或 MetricResult，也不发布最终双报告。三种稳定错误码及其触发边界由[分卷三第 9 节](./2026-07-27-ragas-response-reference-rubric-judge-design.md#9-稳定错误码与处理责任)独占登记。

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

`MetricDispatcher` 读取正式 `metrics.json`，为每个 case 调用分卷三登记的八项实现。所有需要检索输出的 Metric 只从冻结 case 与本次 `CaseObservation` 消费最终融合后有序 chunks；生成端 Metric 不消费 chunks。Accuracy 评分时，Dispatcher 按分卷三的唯一定义提供 \(C_q\)；本卷不复制其物理来源或身份契约。Dispatcher 不在运行层改变参数或补充评分规则。

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

正式 run 使用四个状态：

| 状态 | 进入条件 | 离开条件 |
| --- | --- | --- |
| `running` | preflight 通过并开始运行 | `completed`、`incomplete` 或 `failed` |
| `completed` | 所有 Metric 均完成，且两份报告已经写出 | 终态 |
| `incomplete` | 至少一项 Metric 返回错误，运行继续完成聚合并写出两份报告 | 终态 |
| `failed` | RAG、观测、Recorder、聚合、结果构建、writer、状态记录或发布基础设施发生 fatal 失败 | 终态 |

状态转换固定为：

```text
preflight 通过 -> running -> completed
                         \-> incomplete
                         \-> failed
```

`incomplete` 只表示本次运行已经完成全部 case、聚合和双报告发布，但含有单项 Metric 错误。两份报告必须存在，并明确呈现同一个 run 状态。fatal 优先级固定为 `failed > incomplete > completed`；因此即使已经有 Metric 错误，后续 fatal 仍使 run 成为 `failed`。

### 8.1 `run_status.json` 契约

`run_status.json` 是 run 生命周期的唯一状态记录，正式位置为 `reports/evaluation_baseline/<run_id>/run_status.json`；隐藏 staging 内使用同名文件。文件顶层必须恰好包含以下四个字段，禁止任何额外字段：

| 字段 | 完整契约 |
| --- | --- |
| `schema_version` | 初始固定为字符串 `1.0.0`。 |
| `run_id` | 非空字符串；必须等于本次运行身份，也必须等于最终目录名。 |
| `status` | 仅允许 `running`、`completed`、`incomplete`、`failed`。 |
| `errors` | 数组；每项恰好包含非空字符串 `code` 与非空字符串 `message`，禁止额外字段。`code` 只使用分卷三登记的稳定值域；`message` 可变但必须脱敏，不得包含密钥、完整请求/响应或堆栈。 |

`running`、`completed` 与 `incomplete` 的 run 级 `errors=[]`。`incomplete` 的 Metric 错误只保留在 `report.json` 的 `MetricResult.errors`，不得复制到 `run_status.json`。`failed` 的 `errors` 至少一项且只包含 run 级 fatal：主错误在前，状态记录、发布等次级错误按因果顺序追加。若首次无法创建本文件，或无法写入 `failed` 终态，则 CLI stderr envelope 是事实来源，不得伪造成功的 `run_status.json`。

preflight 失败不创建正式 run，也不创建 `run_status.json`。不支持复用同一 `run_id` 续跑；不得增加 `created_at`、`updated_at`、`details`、`context`、`stack`、恢复字段或任何其他字段。

完整 failed 状态示例：

```json
{
  "schema_version": "1.0.0",
  "run_id": "baseline_20260809_001",
  "status": "failed",
  "errors": [
    {
      "code": "eval.run.rag_execution_failed",
      "message": "被测 RAG 调用失败"
    }
  ]
}
```

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
| `status` | 仅 `completed` 或 `incomplete`；`failed` 不建立该对象 |
| `val_set` | 正式 `val_set.json` 的 `val_set_id` 与 `content_hash` 引用 |
| `metrics_config` | 正式 `metrics.json` 的 schema 版本与配置 hash 引用 |
| `cases` | 全部逐 case 观测及其八项 `MetricResult`，嵌套结构由下表固定 |
| `metric_summaries` | 分卷三返回的八项 `MetricSummary` |

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
5. 在隐藏 staging 目录中把同一个对象交给 `JsonReportWriter`，直接写出 `report.json`。
6. 在同一 staging 目录中把同一个对象交给 `MarkdownReportWriter`，直接写出 `report.md`。
7. `run_status.json`、两份报告与 staging 目录完成 flush/fsync 后，整体 rename 为正式 run 目录，并 fsync 父目录。

`MarkdownReportWriter` 负责把对象中的 run 概况、逐 case 结果、八项汇总和错误证据组织成 Markdown 文件。两个 writer 都只输出最终融合后有序 chunks 的稳定 `chunk_id` 与完整 `text`。Markdown writer 不解析 JSON，也不依赖模板页面、Dashboard、Streamlit、Rich 或旧报告工具。

后续阶段接入 `system_snapshot.json` 时，`JsonReportWriter` 保留 `indexed_documents.source_documents` 与 `indexed_documents.cq_content_hash`；`MarkdownReportWriter` 只展示 `source_documents`，不得展示 C_q hash。该展示差异不改变两个 writer 读取同一个不可变聚合对象的约束。

两份 writer 的一致性验证比较同一对象投影出的 run 身份、输入身份、case 集合、Metric 结果、汇总结果和 run 状态。验证目标是确认两种表达来自同一对象，不是让 Markdown 反向解析 JSON。任一 writer 或发布步骤失败均为 fatal，不发布单份报告；状态记录失败只重试一次，第二次失败以 CLI 报错且不递归记录。各稳定错误码与非 Metric CLI envelope、退出码由分卷三第 9 节定义。

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
8. 实现两个彼此独立的 writer、隐藏 staging 与整目录发布。
9. 验证 `completed`、`incomplete` 与 `failed` 三条终态路径，以及非 Metric CLI 输出。
10. 使用冻结输入运行真实被测 RAG，完成首个 baseline 端到端验收。

实施计划不得在上述任务中重新发明 `val_set`、Metric 或聚合字段；发现缺口时回到对应分卷补齐后再继续。

## 13. 验收检查

- preflight 只调用分卷二、分卷三的正式校验规则。
- `system_snapshot.json` 不出现在第一阶段 preflight、实施步骤或报告契约中。
- 后续阶段的 `system_snapshot.json` 能机械投影当前检索顺序、切分规则、`indexed_documents.source_documents` 与 \(C_q\) hash；`report.json` 同时保留两者，`report.md` 只展示 `source_documents`，不展示 hash，也不复制第二份。
- 每个冻结 case 只运行一次当前被测 RAG。
- Recorder 只保存实际 Query、最终融合后有序 chunks 的稳定 `chunk_id` 与完整 `text`，以及最终回答；数组顺序就是唯一 rank，不补造、去重或重排。
- 所有需要检索输出的 Metric 只消费最终融合后有序 chunks；生成端 Metric 不消费 chunks。
- `cases[]` 每项恰好包含 `case_id`、`observation`、`metric_results`，其中 `observation` 使用本文固定结构，`metric_results` 恰好八项且每项 `case_id` 与父 case 一致。
- 每个 case 调用分卷三登记的全部八项 Metric。
- 任一单项 Metric 错误后，其余 Metric 和后续 case 继续执行。
- 聚合只在全部 case 执行结束后调用，并且只执行分卷三的算法。
- 无单项错误时 run 终态为 `completed`。
- 存在单项错误时 run 终态为 `incomplete`，两份报告仍然存在。
- `run_status.json` 顶层和每项错误均不含额外字段；`incomplete` 的 Metric 错误不复制到该文件，failed 只保存 run 级 fatal 且主错误在前。
- preflight 失败不创建 `run_status.json`；首次状态创建或失败终态写入失败时，CLI stderr envelope 为唯一事实来源；同一 `run_id` 不续跑。
- RAG、观测、Recorder、聚合、结果构建、writer、状态记录或发布 fatal 后 run 为 `failed`；不伪造 MetricResult，且不发布最终双报告或单份报告。
- 双报告只在隐藏 staging 中完成后整目录发布；报告发现逻辑不把 staging 识别为正式 run。
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
| `completed` / `incomplete` / `failed` run 状态 | 设计已确认，尚未实现 |
| JSON 与 Markdown 从同一对象直接写出 | 设计已确认，尚未实现 |
| 真实模型与新评测系统端到端 baseline | 尚未验证 |

本卷不记录依赖安装日志、测试计数或临时 smoke 结果。实现状态只能由当前代码和真实验收证据更新。
