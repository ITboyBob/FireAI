# 分卷三：Metric 与评分契约

> **文档类型**：专项架构设计分卷
> **日期**：2026-08-09
> **版本**：v2.0
> **状态**：Under Review

## 0. 卷册导航与本卷边界

- [返回设计总卷](../../新评测系统设计总卷.md)：确认八个评测维度与四份文档的职责顺序。
- [分卷一：评测执行与报告架构](./2026-07-23-evaluation-optimization-loop-architecture-design.md)：读取何时调用评分、怎样继续运行以及怎样写出结果。
- [分卷二：val_set 生成与冻结](./2026-07-27-ragas-val-set-query-generation-design.md)：读取 Query、参考答案和完整 relevance ground truth 的来源。
- 当前分卷：独占 `metrics.json`、八项 Metric 的输入与算法、`MetricResult`、`MetricSummary`、逐 Metric 聚合、稳定错误码及未决错误边界。

本卷不生成 `val_set.json`，不安排评测步骤，不定义 run 状态、输出目录或 Markdown 格式。

## 1. 决策结论

一份 `metrics.json` 固定八项 Metric 的 ID、输入、参数、计分和聚合规则。评分器读取分卷二冻结的 val case 与分卷一捕获的 RAG 观测，逐项返回统一 `MetricResult`；随后按同一 `metric_id` 聚合全部 val cases，返回 `MetricSummary`。

任何单项评分失败都返回 `status=error` 与空分数，不终止评测调用链；后续 case 和其他 Metric 继续执行。只要该 Metric 任一 case 的 `status=error` 或 `normalized_score=null`，其 `MetricSummary` 就返回 `status=incomplete` 与空均值。分卷一只能消费这一结果，不得重新计算或静默排除失败 case。

Ragas `RubricsScoreWithReference` 是八项 Metric 之一，与其他七项共享结果和聚合契约，不另立第二套评分模型。

## 2. 单一事实来源

本卷是 `metrics.json`、八项评分定义、`MetricResult`、`MetricSummary` 和逐 Metric 聚合算法的唯一事实来源。总卷只列出评测维度并导航到本卷；分卷一只调用本卷定义的评分器；分卷二只产生本卷读取的 val case。描述冲突时以本卷为准。

## 3. `metrics.json` 契约

顶层 `schema_version` 固定为 `1.0.0`，`metrics` 必须包含且仅包含以下八个稳定 ID：

1. `retrieval_precision`
2. `retrieval_recall`
3. `trulens_context_relevance_with_cot_reasons`
4. `retrieval_accuracy`
5. `retrieval_map`
6. `retrieval_mrr`
7. `deepeval_answer_relevancy`
8. `ragas_rubrics_score_with_reference`

每项配置必须保存：

| 字段 | 内容 |
| --- | --- |
| `metric_id` | 上述稳定 ID |
| `implementation` | 固定公式、公开类或方法 |
| `inputs` | 实际读取的业务输入 |
| `parameters` | `k=5`、固定依赖版本与 Judge 参数 |
| `score_contract` | raw/normalized 范围、空输入和错误规则 |
| `details_contract` | `details` 的固定结构、内容来源与空值边界 |
| `aggregation` | 单 case 内计算与跨 case 聚合方式 |
| `rubrics` | 仅 Ragas 项保存完整五档英文 rubric |

`metrics.json` 的 canonical JSON 计算 SHA-256 配置 hash。Ragas 的五档 rubric 必须进入 hash；字段顺序、空白与非 ASCII 转义差异不得改变 hash。

## 4. 公共输入与不变量

对 Query \(q\)：

- \(R_q\) 是最终融合后的有序 Top-5 检索结果，且 `chunk_id` 唯一；重复 ID 使依赖 \(R_q\) 的对应 Metric 返回错误，不得静默去重。
- \(G_q\) 是分卷二随 val case 冻结的完整 relevance ground truth，必须非空；空集合应在执行评分前被分卷一的 preflight 拒绝。它默认等于 Ragas scenario 的 `source_chunk_ids` 所对应 chunks；这是 Fire 评测协议的业务假设，不是 Ragas 自动证明的完整性，可导致检索指标系统性偏差。
- \(C_q\) 是当前仓库全部 chunks 集合。唯一物理来源是 `Settings.data_dir / "chunks"`：`Settings.data_dir` 默认为 `data`，按文件名顺序读取该目录下全部 `*.jsonl` 的所有 chunk 记录，与 `scripts/build_index.py::load_chunks` 一致。\(G_q\) 是随 val case 冻结的相关 chunk 集合；\(R_q\) 是本次 RAG 执行产生的最终融合结果。
- \(C_q\) 不设立冻结时点。当后续阶段生成 `system_snapshot.json` 时，`indexed_documents.cq_content_hash` 标识该次快照记录的 \(C_q\) 内容，但不引入额外冻结时点。
- `cq_content_hash` 按以下唯一规则计算：读取 `Settings.data_dir / "chunks"` 下全部 `*.jsonl`，解析每个完整 chunk 对象；先校验 `chunk_id` 全局唯一，再按 `chunk_id` 升序排列；每个对象使用 UTF-8、key 排序、紧凑分隔符且不转义非 ASCII 的 canonical JSON；对完整 canonical JSON 数组计算 SHA-256，保存为 `sha256:<64hex>`。
- 后续阶段中，机器友好的 `report.json` 同时保留 `system_snapshot.indexed_documents.source_documents` 与 `system_snapshot.indexed_documents.cq_content_hash`；人类友好的 `report.md` 只引用和展示 `source_documents`，不得展示 C_q hash。两份报告均不另建独立的 \(C_q\) 文件清单或重复 hash 字段。`system_snapshot.json` 仍只在评测数据集生成完成后进入后续阶段，不纳入第一阶段实施计划。
- 所有读取检索输出的 Metric 只能消费最终 \(R_q\)；禁止读取融合前 chunks、融合前 rank、candidate IDs，或建立绕过 \(R_q\) 的隐藏旁路。
- DeepEval 与 Ragas 两个生成端 Metric 不消费 \(R_q\)，也不读取任何融合前检索数据。
- 分数越界不得 clamp，必须返回该项错误。

## 5. 八项 Metric

### 5.1 `retrieval_precision`

- 输入：\(R_q\) 与 \(G_q\) 的 `chunk_id`。
- 公式：\(\mathrm{Precision@5}(q)=|R_q\cap G_q|/|R_q|\)。
- 输出：`[0,1]`；\(R_q\) 为空时为 `0`。
- details：恒为 `null`；输入错误由统一 `errors` 说明。

### 5.2 `retrieval_recall`

- 输入：\(R_q\) 与 \(G_q\) 的 `chunk_id`。
- 公式：\(\mathrm{Recall@5}(q)=|R_q\cap G_q|/|G_q|\)。
- 输出：`[0,1]`；\(R_q\) 为空时为 `0`。
- details：恒为 `null`；\(G_q\) 为空不进入评分。

### 5.3 `trulens_context_relevance_with_cot_reasons`

- 输入：同一 Query 与 \(R_q\) 中每个 chunk 的文本；不读取 \(G_q\)、生成回答、参考答案或 rank。
- 实现：使用 TruLens `2.9.0` 的 `context_relevance_with_cot_reasons` 逐 chunk 调用 Judge；每次真实返回 `(normalized_score, metadata)`，`chunk_id` 由 Fire 根据输入 \(R_q\) 关联，case 分数为全部 `normalized_score` 的等权平均。
- 输出：`raw_score=null`；`normalized_score` 为 case 均值；非空检索时 `details={chunks:[{chunk_id, normalized_score, reason}]}`，数组顺序与 \(R_q\) 一致且不设置 `rank`。
- 边界：`metadata` 缺少非空 `reason` 时该 Metric 返回 `error`，防止完成态缺少必需字段；\(R_q\) 为空时不调用 Judge，完成态分数为 `0`，`details={chunks:[]}`；错误时 `details=null`。Judge reason 只是解释，不得称为已核验引文。

### 5.4 `retrieval_accuracy`

- 输入：\(R_q\)、\(G_q\) 的 `chunk_id`，以及本次评分调用瞬时提供的 \(C_q\)。
- 分类：在 \(C_q\) 内，以 \(R_q\) 为预测正例、\(G_q\) 为真实正例，计算 TP、TN、FP、FN。
- 公式：\(\mathrm{Accuracy}(q)=(TP+TN)/(TP+TN+FP+FN)\)。
- 输出：`[0,1]`；`details` 恒为 `null`。
- 边界：分母为 `0` 或 \(R_q\) 中出现不属于 \(C_q\) 的 ID 时返回错误；评分器不得改变 \(C_q\)。

### 5.5 `retrieval_map`

- 输入：有序 \(R_q\) 与 \(G_q\) 的 `chunk_id`。
- 公式：\(\mathrm{AP@5}(q)=\sum_{r=1}^{|R_q|}\mathrm{Precision@r}(q)\times rel_q(r)/|G_q|\)。
- 输出：单 case AP@5 为 `[0,1]`；\(R_q\) 为空或无命中时为 `0`；`details` 恒为 `null`。
- 跨 case：全部 AP@5 等权平均后形成本 Metric 的 MAP@5。

### 5.6 `retrieval_mrr`

- 输入：有序 \(R_q\) 与 \(G_q\) 的 `chunk_id`。
- 公式：第一个相关 chunk 的 rank 为 \(r\) 时，\(\mathrm{RR@5}(q)=1/r\)。
- 输出：单 case RR@5 为 `[0,1]`；\(R_q\) 为空或无命中时为 `0`；`details` 恒为 `null`。
- 跨 case：全部 RR@5 等权平均后形成本 Metric 的 MRR@5。

### 5.7 `deepeval_answer_relevancy`

- 输入：`LLMTestCase.input=Query`、`LLMTestCase.actual_output=生成回答`；不读取参考答案、contexts 或 \(G_q\)。
- 实现：DeepEval `4.1.4` `AnswerRelevancyMetric`；按 `verdict != "no"` 的数量除以 verdict 总数计分，因此 `yes` 与 `idk` 均计为相关，空 verdict 返回 `1`。
- 参数：`include_reason=true`、`strict_mode=false`、`async_mode=true`。
- 输出：调用完成后从 `metric.score` 读取 `[0,1]` 业务分，从 `metric.reason` 读取解释；`raw_score=null`，`normalized_score=metric.score`，`details={reason: metric.reason}`；错误时 `details=null`。不得把 DeepEval 内部 threshold/success 转成 Fire 结果。
- 测试隔离：pytest、CI 或默认配置验证必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。

### 5.8 `ragas_rubrics_score_with_reference`

- 输入：`user_input=Query`、`response=生成回答`、`reference=分卷二脚本生成并随 val case 冻结的参考答案`；不得传入 `retrieved_contexts` 或 `reference_contexts`。
- 实现：Ragas `0.4.3` `RubricsScoreWithReference`；使用 `AsyncOpenAI` 客户端与 `llm_factory` 建立独立 Judge，调用 `await metric.ascore(...)`。
- 参数：读取 `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL`，`temperature=0`；默认只执行一次逻辑评分。
- 输出：从真实返回对象 `result.value` 读取 `raw_score`，范围 `1–5`；`normalized_score=(raw_score-1)/4`；`details={reason: result.reason}`；错误时 `details=null`。
- 边界：不读取来源 chunks，不参与分卷二的数据集生成与冻结，也不调用其他 Ragas Metric。

## 6. Ragas rubric

- 使用 `RubricsScoreWithReference`，它等价于 `DomainSpecificRubrics(with_reference=True)`。
- 采用 [Ragas `0.4.3` 官方源码](https://github.com/vibrantlabsai/ragas/blob/v0.4.3/src/ragas/metrics/collections/domain_specific_rubrics/util.py)中的默认五档 reference-based rubric 语义：从“完全错误、无关或不符合参考答案”逐档提升到“完全准确、完整符合参考答案且清晰、充分、详细”。
- Ragas `0.4.3` 的完整五档英文 rubric 必须原样写入 `metrics.json` 的本 Metric `rubrics`，并参与配置 hash；不得只保存中文摘要或依赖上游运行时默认。
- `metrics.json` 顶层固定 `schema_version=1.0.0` 与 `metrics`；本项与其他 Metric 一样保存 `metric_id`、`implementation`、`inputs`、`parameters`、`score_contract`、`details_contract`、`aggregation`。
- 不导入或直接实例化 `DomainSpecificRubrics`；Fire 使用公开便利类 `RubricsScoreWithReference` 表达已确认的 reference-based 模式。

| Key | 完整英文文本 | Source |
| --- | --- | --- |
| `score1_description` | `The response is entirely incorrect, irrelevant, or does not align with the reference in any meaningful way.` | Ragas `0.4.3` |
| `score2_description` | `The response partially matches the reference but contains major errors, significant omissions, or irrelevant information.` | Ragas `0.4.3` |
| `score3_description` | `The response aligns with the reference overall but lacks sufficient detail, clarity, or contains minor inaccuracies.` | Ragas `0.4.3` |
| `score4_description` | `The response is mostly accurate, aligns closely with the reference, and contains only minor issues or omissions.` | Ragas `0.4.3` |
| `score5_description` | `The response is fully accurate, completely aligns with the reference, and is clear, thorough, and detailed.` | Ragas `0.4.3` |

## 7. `MetricResult` 契约

每个 case 的每项评分必须返回一个 `MetricResult`；顶层字段固定且仅为 `case_id`、`metric_id`、`raw_score`、`normalized_score`、`status`、`errors`、`details`：

| 字段 | 契约 |
| --- | --- |
| `case_id` | 对应正式 val case |
| `metric_id` | 对应 `metrics.json` 中的稳定 ID |
| `raw_score` | 原生分；操作错误时为 `null` |
| `normalized_score` | `[0,1]`；操作错误时为 `null` |
| `status` | 仅 `completed` 或 `error` |
| `errors` | 结构化错误数组；正常完成时为空数组 |
| `details` | 本 Metric 契约明确要求的诊断结构；无诊断或错误时为 `null` |

每个 `errors` 项至少包含稳定 `code` 与人类可读 `message`。只有第 9 节的 `eval.metric.*` 值域可进入 `MetricResult.errors`；`code` 稳定，`message` 允许变化但必须脱敏。错误堆栈、密钥、完整请求或服务响应不得进入结果对象。

完成态与错误态的分数、详情字段固定如下：

| Metric | `status` | `raw_score` | `normalized_score` | `details` |
| --- | --- | --- | --- | --- |
| Precision / Recall / Accuracy / MAP / MRR | `completed` | `null` | 各自 `[0,1]` 业务分 | `null` |
| TruLens | `completed` | `null` | `[0,1]` case 均值 | 非空检索为 `{chunks:[{chunk_id, normalized_score, reason}]}`；空检索为 `{chunks:[]}` |
| DeepEval | `completed` | `null` | `metric.score` | `{reason: metric.reason}` |
| Ragas | `completed` | `result.value`，范围 `1–5` | `(raw_score-1)/4` | `{reason: result.reason}` |
| 任一 Metric | `error` | `null` | `null` | `null` |

确定性 Metric、合法空检索和错误均不得补造机械 reason。正常 `raw_score=null` 是合法完成态，不得据此判定结果不完整。

## 8. `MetricSummary` 与聚合

同一 `metric_id` 的全部 val cases 必须聚合为一个 `MetricSummary`：

| 字段 | 契约 |
| --- | --- |
| `metric_id` | 对应 `metrics.json` 中的稳定 ID |
| `case_count` | 正式 val case 总数 |
| `error_case_count` | `MetricResult.status=error` 的 case 数 |
| `mean_score` | 全部 case 的 `normalized_score` 等权算术平均；任一值为 `null` 时整体为 `null` |
| `status` | 任一 `MetricResult.status=error` 或 `normalized_score=null` 时为 `incomplete`；否则为 `completed` |

聚合只读取 `normalized_score`，不得读取 `raw_score` 判断完整性或计算均值；也不得按 Query 类型、chunk 数、Judge 调用次数或生成长度加权，或删除失败 case 后重算。MAP@5 与 MRR@5 分别使用 AP@5、RR@5 的全部 case 值按本节规则聚合。

## 9. 稳定错误码与处理责任

全部错误码使用小写点分命名空间；`code` 值稳定，人类可读 `message` 允许变化但必须脱敏。本节登记的稳定错误码总数为 42（原有 28 个，本轮新增 14 个）。本节是新评测四文档已确定错误码、选择优先级与处理边界的唯一事实来源；分卷一和分卷二只执行职责内动作并引用本节，不复制值域。

### 9.1 `val_set.json` 生成与发布

| 阶段 | 稳定 `code` | 触发条件 | 固定动作 |
| --- | --- | --- | --- |
| 生成 | `eval.val_set.generate.source_chunks_empty` | 当前仓库 chunks 为空 | hard fail，旧正式文件保持不变 |
| 生成 | `eval.val_set.generate.source_chunk_id_duplicate` | 输入 `chunk_id` 重复 | hard fail，旧正式文件保持不变 |
| 生成 | `eval.val_set.generate.ragas_generation_failed` | Ragas 生成失败 | 终止生成，不发布部分结果，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.schema_invalid` | 临时产物 schema 非法 | 拒绝原子替换，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.val_set_id_invalid` | `val_set_id` 校验失败 | 拒绝原子替换，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.case_id_invalid` | 任一 `case_id` 校验失败 | 拒绝原子替换，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.content_hash_invalid` | `content_hash` 校验失败 | 拒绝原子替换，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.case_count_mismatch` | `len(cases) != val_set_case_count` | 拒绝原子替换，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.temp_write_failed` | 同目录临时文件创建、写入、flush 或 fsync 失败 | 不执行 replace，旧正式文件保持不变 |
| 发布 | `eval.val_set.publish.atomic_replace_failed` | 已校验的同目录临时文件 replace 失败 | 旧正式文件保持不变；如清理也失败，追加清理失败码 |
| 发布 | `eval.val_set.publish.temp_cleanup_failed` | replace 失败后清理临时文件失败 | 作为第二个错误追加；不改变 replace 失败结论 |
| 发布 | `eval.val_set.publish.durability_unconfirmed` | replace 成功但父目录 fsync 失败 | 不回滚；不得声称旧正式文件保持不变 |

发布固定遵循“同目录临时文件 write/flush/fsync → 完整契约校验 → replace → 父目录 fsync”。发布失败同时匹配专用码与 `eval.val_set.publish.schema_invalid` 时，必须选择专用码。

### 9.2 Preflight

| 稳定 `code` | 触发条件 |
| --- | --- |
| `eval.preflight.val_set_missing` | `val_set.json` 不存在 |
| `eval.preflight.val_set_unreadable` | `val_set.json` 不可读或无法解析 |
| `eval.preflight.val_set_contract_invalid` | `val_set.json` 其他契约校验失败的兜底码 |
| `eval.preflight.metrics_config_missing` | `metrics.json` 不存在 |
| `eval.preflight.metrics_config_unreadable` | `metrics.json` 不可读或无法解析 |
| `eval.preflight.metrics_config_contract_invalid` | `metrics.json` 其他契约校验失败的兜底码 |
| `eval.preflight.metric_set_mismatch` | Metric 集合不是总卷固定的八项 |
| `eval.preflight.relevance_ground_truth_empty` | \(G_q\) 为空 |
| `eval.preflight.case_scoring_input_invalid` | case 不能提供声明的评分输入 |
| `eval.preflight.rag_entrypoint_unavailable` | 被测 RAG 运行入口不可用 |
| `eval.preflight.rag_index_unavailable` | 被测 RAG 所需索引不可用 |
| `eval.preflight.run_id_conflict` | 目标 `run_id` 会覆盖已有报告目录 |

Preflight 收集所有安全可评估错误，而非首错即停：上游文件缺失时不解析该文件，配置无法成立时不执行依赖配置的 case 检查，RAG 入口不可用时不继续索引检查，`run_id` 冲突独立检查；不调用真实 RAG、Judge 或 Metric。汇总顺序固定为 val_set 文件错误、metrics 文件错误、`metric_set_mismatch`、`relevance_ground_truth_empty`、`case_scoring_input_invalid`、RAG 入口、RAG 索引、`run_id` 冲突。每个 validator 对每个逻辑目标最多产生一次错误；汇总器不得按可变 `message` 进行事后去重。任一 preflight 错误都固定为：不创建正式 run，不调用 RAG 或任何 Metric，不写出报告。同一失败同时匹配专用码与 `*_contract_invalid` 兜底码时，必须选择专用码。

### 9.3 Metric

| 稳定 `code` | 触发条件 |
| --- | --- |
| `eval.metric.retrieved_chunk_id_duplicate` | \(R_q\) 内 `chunk_id` 重复 |
| `eval.metric.input_invalid` | 未被专用码覆盖的单项 Metric 输入错误 |
| `eval.metric.dependency_call_failed` | Judge 或其他 Metric 依赖调用失败 |
| `eval.metric.dependency_response_parse_failed` | 依赖返回无法解析为本卷契约 |
| `eval.metric.score_out_of_range` | 返回分数超出契约范围 |
| `eval.metric.trulens_reason_missing` | TruLens `metadata` 缺少非空 `reason` |
| `eval.metric.accuracy_zero_denominator` | Accuracy 分母为 `0` |
| `eval.metric.accuracy_retrieved_chunk_outside_corpus` | \(R_q\) 出现不属于 \(C_q\) 的 `chunk_id` |

同一 Metric 失败同时匹配专用码和通用码时，必须选择专用码。`status=completed` 时 `errors=[]`；`status=error` 时 `errors` 恰好一个元素，并返回 `raw_score=null`、`normalized_score=null`、`details=null`。主错误选择优先级依次为专项输入错误、`eval.metric.input_invalid`、`eval.metric.dependency_call_failed`、`eval.metric.trulens_reason_missing`、`eval.metric.dependency_response_parse_failed`、`eval.metric.score_out_of_range`，以免同一根因被级联展开。分卷一继续其他 Metric 和后续 case；对应 `MetricSummary` 与 run 标记为 `incomplete`，两份报告仍必须写出。

### 9.4 Run 生命周期与非 Metric CLI

| 阶段 | 稳定 `code` | 触发条件 | 固定动作 |
| --- | --- | --- | --- |
| 初始化 | `eval.run.initialization_failed` | 创建隐藏 staging 目录或首次状态记录失败 | 终止，不发布报告 |
| RAG 执行 | `eval.run.rag_execution_failed` | 调用被测 RAG 失败 | 标记 `failed`，停止后续步骤，不伪造 MetricResult，不发布报告 |
| 观测捕获 | `eval.run.observation_capture_failed` | 无法取得完整 Query、最终 chunks 或回答 | 标记 `failed`，停止后续步骤，不伪造 MetricResult，不发布报告 |
| 观测记录 | `eval.run.observation_record_failed` | Recorder 无法验证、冻结或保存观测 | 标记 `failed`，停止后续步骤，不伪造 MetricResult，不发布报告 |
| 聚合 | `eval.run.aggregation_failed` | 聚合失败 | 标记 `failed`，不发布报告 |
| 结果构建 | `eval.run.result_build_failed` | 无法建立不可变聚合对象 | 标记 `failed`，不发布报告 |
| JSON 报告 | `eval.run.json_report_write_failed` | JSON 渲染或写入失败 | 标记 `failed`，不发布单份报告 |
| Markdown 报告 | `eval.run.markdown_report_write_failed` | Markdown 渲染或写入失败 | 标记 `failed`，不发布单份报告 |
| 状态记录 | `eval.run.status_record_write_failed` | 后续状态记录更新失败 | 仅重试记录一次；再次失败以 CLI 报错，不递归记录新错误 |
| 发布 | `eval.run.publish_failed` | staging 目录 fsync、整目录 rename 或父目录 fsync 失败 | 标记 `failed`，不将 staging 识别为正式 run |

`failed` 的优先级高于 `incomplete`，高于 `completed`；故已经出现单项 Metric 错误后发生上述任一 fatal 失败，终态仍为 `failed`。`completed` 与 `incomplete` 的双报告须在隐藏 staging 目录完成并 flush/fsync 后，整体 rename 到正式 run 目录，再 fsync 父目录；禁止先逐文件发布、失败后回删。隐藏 staging 目录不得被报告发现逻辑视为正式 run。

非 Metric 错误固定使用单行 stderr JSON envelope：顶层仅 `schema_version`、`status`、`run_id`、`errors`；其中 `errors[]` 每项仅 `code`、`message`。stdout 不得混入错误。退出码固定为：`0` 表示数据集生成成功或 run 为 `completed`；`1` 表示 val_set 发布/preflight 失败、run 为 `incomplete` 或 `failed`；`2` 表示 argparse 参数或用法错误。

`run_status.json` 的位置、完整 schema、状态与错误字段约束只由[分卷一 §8.1](./2026-07-23-evaluation-optimization-loop-architecture-design.md#81-run_statusjson-契约)定义；本卷只提供其中 `code` 可选的稳定值域。

### 9.5 最小测试约束

- 每个已列 `code` 至少有一个可重复的触发用例，并断言对应阶段的固定动作。
- 同时匹配专用码与通用/兜底码时，测试必须断言只选择专用码。
- 生成与 preflight 测试必须断言其错误不进入 `MetricResult.errors`；Metric 错误测试必须断言 `completed` 的空 errors、`error` 的唯一主错误、统一空分数/空 details、继续调度、summary/run `incomplete` 与双报告写出。
- Preflight 测试必须覆盖依赖门禁、稳定多错误顺序与每目标一次；val_set 发布测试必须覆盖临时文件写入失败、replace 失败与清理失败组合，以及 replace 成功后父目录 fsync 失败的持久性未确认。
- Run 测试必须覆盖三类 RAG/观测 fatal、聚合/构建/两类 writer fatal、状态记录一次重试和整目录发布；断言 fatal 优先于 `incomplete`、不伪造 MetricResult、不发布单份报告。CLI 测试必须断言 stderr 单行 envelope、stdout 无错误及三类退出码。
- 错误 `message` 测试必须确认不含密钥、完整请求/响应或错误堆栈。
- `run_status.json` 测试必须按分卷一 §8.1 断言位置、四个顶层字段、错误项双字段、状态特定 errors、目录内容与失败时 CLI 事实来源；不得从本卷新增字段或错误码。

## 10. 依赖与配置边界

- TruLens 项固定 `trulens-core==2.9.0` 与 `trulens-feedback==2.9.0`，通过 Fire provider 读取 Judge 配置。
- DeepEval 项固定 `deepeval==4.1.4`；任何 pytest、CI 或默认配置验证在 import 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。
- Ragas 项固定 `ragas==0.4.3`、`langchain-community==0.4.1` 与 `openai==2.30.0`；公开导入仅使用 `from ragas.llms import llm_factory` 与 `from ragas.metrics.collections import RubricsScoreWithReference`。
- Fire 评分代码不得直接导入 `DomainSpecificRubrics`、`ragas.evaluate`、LangChain wrapper 或任何 LangChain 类。
- 分卷二的数据集生成 LLM 使用 `WS_RAG_QUESTION_GENERATOR_*`，本卷 Judge 使用 `WS_RAG_JUDGE_*`；两者建立独立客户端和 LLM 实例。

## 11. 实施验收

- 校验 `metrics.json` 恰好包含八项配置，且配置 hash 能检测 rubric 或参数变化。
- 验证 `cq_content_hash` 在文件顺序、JSONL 记录顺序、对象 key 顺序或空白变化时保持不变，任一完整 chunk 对象内容变化时 hash 改变，且重复 `chunk_id` 在计算前被拒绝；`report.json` 同时保留 `system_snapshot.indexed_documents.source_documents` 与 `system_snapshot.indexed_documents.cq_content_hash`，`report.md` 只展示 `source_documents` 且不展示 hash。
- 验证所有读取检索输出的 Metric 只消费最终融合后的有序 \(R_q\)，且没有融合前 chunks、融合前 rank、candidate IDs 或隐藏旁路；DeepEval 与 Ragas 不消费 \(R_q\)。
- 对每项 Metric 验证正常、空检索、重复 `chunk_id`、依赖异常和越界分数路径。
- 验证一个 case 的单项错误不会阻止后续 case 或其他 Metric 返回结果。
- 验证完成态与错误态的 `raw_score`、`normalized_score`、`details` 字段矩阵；正常 `raw_score=null` 不触发 `incomplete`，任一 `status=error` 或 `normalized_score=null` 都产生 `mean_score=null`、`status=incomplete`，且失败 case 不会被排除。
- 使用真实 Judge LLM 验证 TruLens `(normalized_score, metadata)`、DeepEval `metric.score/metric.reason` 与 Ragas `result.value/result.reason` 的接口映射和错误路径；公开 import smoke 不得代替真实调用验收。
