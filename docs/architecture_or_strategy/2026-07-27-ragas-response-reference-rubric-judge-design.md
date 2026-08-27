# 分卷三：Metric 与评分契约

> **文档类型**：专项架构设计分卷
> **日期**：2026-08-09
> **版本**：v2.0
> **状态**：Under Review

## 0. 卷册导航与本卷边界

- [返回设计总卷](../../新评测系统设计总卷.md)：确认八个评测维度、`eval_set/` 与两份分卷的职责顺序。
- [分卷一：评测执行与报告架构](./2026-07-23-evaluation-optimization-loop-architecture-design.md)：读取何时调用评分、怎样继续运行以及怎样写出结果。
- [评测数据集规范](../../eval_set/CODEMAP.md)：读取评测数据集独立生成的规范与边界。
- 当前分卷：独占 `metrics.json`、八项 Metric 的输入与算法、`MetricResult`、`MetricSummary`、逐 Metric 聚合、稳定错误码及未决错误边界。

本卷不生成评测数据集，不安排评测步骤，不定义 run 状态、输出目录或 Markdown 格式。

## 1. 决策结论

一份 `metrics.json` 固定八项 Metric 的 ID、输入、参数、计分和聚合规则。评分器读取按 `eval_set/` 规范独立生成的评测 case 与分卷一捕获的 RAG 观测，逐项返回统一 `MetricResult`；随后按同一 `metric_id` 聚合全部评测 case，返回 `MetricSummary`。

任何单项评分失败都返回 `status=error` 与空分数，不终止评测调用链；后续 case 和其他 Metric 继续执行。只要该 Metric 任一 case 的 `status=error` 或 `normalized_score=null`，其 `MetricSummary` 就返回 `status=incomplete` 与空均值。分卷一只能消费这一结果，不得重新计算或静默排除失败 case。

Ragas `RubricsScoreWithReference` 是八项 Metric 之一，与其他七项共享结果和聚合契约，不另立第二套评分模型。

## 2. 单一事实来源

本卷是 `metrics.json`、八项评分定义、`MetricResult`、`MetricSummary` 和逐 Metric 聚合算法的唯一事实来源。总卷只列出评测维度并导航到本卷；分卷一只调用本卷定义的评分器；评测数据集由 `eval_set/` 独立生成。描述冲突时以本卷为准。

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

- \(R_q\) 是每个 Query 最终融合后的有序、最多 5 个 chunks 的检索结果，且 `chunk_id` 唯一；重复 ID 使依赖 \(R_q\) 的对应 Metric 返回错误，不得静默去重。“5”只表示该最终列表截断，不是 Precision/Recall 的名称，也不是五个问题或五次运行。
- \(G_q\) 是仓库现存 chunk 集合。preflight 首次读取 `Settings.data_dir / "chunks"` 下全部 `*.jsonl` 的完整 chunk 对象，校验 `chunk_id` 全局唯一并建立不可变系统 snapshot；该 snapshot 标识本次 run 的 \(G_q\)。
- \(C_q\) 是评测数据集 answer 对应的 chunk，必须非空；空集合应在执行评分前被分卷一的 preflight 拒绝。\(C_q\) 与 \(G_q\) 均不绑定特定字段。
- 系统 snapshot 的身份按以下规则机械确定：完整 chunk 对象按 `chunk_id` 升序排列，每个对象使用 UTF-8、key 排序、紧凑分隔符且不转义非 ASCII 的 canonical JSON，对完整 canonical JSON 数组计算 SHA-256。字段名与报告投影位置不是 \(G_q\) 或 \(C_q\) 的业务定义。
- `report.json` 保留系统 snapshot 的完整投影；人类友好的 `report.md` 只展示 `source_documents`。两份报告均不另建 \(G_q\) 或 \(C_q\) 的独立文件或特定字段清单。
- preflight 逐 case 在该 run 内 \(G_q\) snapshot 上机械校验 \(C_q \subseteq G_q\)；任一 \(C_q\) 的 `chunk_id` 不在 \(G_q\) 时，不进入评分或 run 生命周期。
- 所有读取检索输出的 Metric 只能消费最终 \(R_q\)；禁止读取融合前 chunks、融合前 rank、candidate IDs，或建立绕过 \(R_q\) 的隐藏旁路。
- DeepEval 与 Ragas 两个生成端 Metric 不消费 \(R_q\)，也不读取任何融合前检索数据。两者只读取 `answer_text=ChatResponse.conclusion.strip()`，该字符串必须非空；`citations`、`scope`、`uncertainty`、`evidence` 不拼接或传入，尤其不得泄漏 `evidence`。
- 分数越界不得 clamp，必须返回该项错误。

## 5. 八项 Metric

### 5.1 `retrieval_precision`

- 输入：\(R_q\) 与 \(C_q\) 的 `chunk_id`。
- 公式：\(\mathrm{Precision}(q)=|R_q\cap C_q|/|R_q|\)。
- 输出：`[0,1]`；\(R_q\) 为空时为 `0`。
- details：恒为 `null`；输入错误由统一 `errors` 说明。

### 5.2 `retrieval_recall`

- 输入：\(R_q\) 与 \(C_q\) 的 `chunk_id`。
- 公式：\(\mathrm{Recall}(q)=|R_q\cap C_q|/|C_q|\)。
- 输出：`[0,1]`；\(R_q\) 为空时为 `0`。
- details：恒为 `null`；\(C_q\) 为空不进入评分。

### 5.3 `trulens_context_relevance_with_cot_reasons`

- 输入：同一 Query 与 \(R_q\) 中每个 chunk 的文本；不读取 \(C_q\)、生成回答、参考答案或 rank。
- 实现：使用 TruLens `2.9.0` 的 `context_relevance_with_cot_reasons` 逐 chunk 调用 Judge；每次真实返回 `(normalized_score, metadata)`，`chunk_id` 由 Fire 根据输入 \(R_q\) 关联，case 分数为全部 `normalized_score` 的等权平均。
- Judge transport：使用 §10.1 的 `FireTruLensProvider`；Fire 只负责请求/响应边界，不修改 TruLens prompt、rubric、评分或聚合。
- 输出：`raw_score=null`；`normalized_score` 为 case 均值；非空检索时 `details={chunks:[{chunk_id, normalized_score, reason}]}`，数组顺序与 \(R_q\) 一致且不设置 `rank`。
- 边界：`metadata` 缺少非空 `reason` 时该 Metric 返回 `error`，防止完成态缺少必需字段；\(R_q\) 为空时不调用 Judge，完成态分数为 `0`，`details={chunks:[]}`；错误时 `details=null`。Judge reason 只是解释，不得称为已核验引文。

### 5.4 `retrieval_accuracy`

- 输入：\(R_q\)、\(C_q\) 的 `chunk_id`，以及 preflight 建立的同一不可变 run 内 \(G_q\) snapshot。
- 分类：在 \(G_q\) 内，以 \(R_q\) 为预测正例、\(C_q\) 为真实正例，计算 TP、TN、FP、FN。
- 公式：\(\mathrm{Accuracy}(q)=(TP+TN)/(TP+TN+FP+FN)\)。
- 输出：`[0,1]`；`details` 恒为 `null`。
- 边界：分母为 `0` 或 \(R_q\) 中出现不属于 \(G_q\) 的 ID 时返回错误；评分器不得改变 \(G_q\)。

### 5.5 `retrieval_map`

- 输入：有序 \(R_q\) 与 \(C_q\) 的 `chunk_id`。
- 公式：\(\mathrm{AP@5}(q)=\sum_{r=1}^{|R_q|}\mathrm{Precision@r}(q)\times rel_q(r)/\min(|C_q|,5)\)。
- 输出：单 case AP@5 为 `[0,1]`；\(R_q\) 为空或无命中时为 `0`；`details` 恒为 `null`。
- 跨 case：全部 AP@5 等权平均后形成本 Metric 的 MAP@5。

### 5.6 `retrieval_mrr`

- 输入：有序 \(R_q\) 与 \(C_q\) 的 `chunk_id`。
- 公式：第一个相关 chunk 的 rank 为 \(r\) 时，\(\mathrm{RR@5}(q)=1/r\)。
- 输出：单 case RR@5 为 `[0,1]`；\(R_q\) 为空或无命中时为 `0`；`details` 恒为 `null`。
- 跨 case：全部 RR@5 等权平均后形成本 Metric 的 MRR@5。

### 5.7 `deepeval_answer_relevancy`

- 评测关系：Answer Relevancy 评估回答相对 Query 的相关性。
- 输入：`LLMTestCase.input=Query`、`LLMTestCase.actual_output=answer_text`；不读取参考答案、retrieved/reference contexts、\(R_q\) 或 \(C_q\)。
- 实现：DeepEval `4.1.4` `AnswerRelevancyMetric`；按 `verdict != "no"` 的数量除以 verdict 总数计分，因此 `yes` 与 `idk` 均计为相关，空 verdict 返回 `1`。
- Judge transport：显式将 §10.2 的 `FireDeepEvalJudge` 注入 `AnswerRelevancyMetric(model=...)`，不使用 DeepEval 默认模型或 `OPENAI_API_KEY`。
- 参数：`include_reason=true`、`strict_mode=false`、`async_mode=true`。
- 输出：调用完成后从 `metric.score` 读取 `[0,1]` 业务分，从 `metric.reason` 读取解释；`raw_score=null`，`normalized_score=metric.score`，`details={reason: metric.reason}`；错误时 `details=null`。不得把 DeepEval 内部 threshold/success 转成 Fire 结果。
- 测试隔离：pytest、CI 或默认配置验证必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。

### 5.8 `ragas_rubrics_score_with_reference`

- 评测关系：Response—Reference Answer 评估回答相对参考答案的正确性、完整性和清晰程度。
- 输入：`user_input=Query`、`response=answer_text`、`reference=评测数据集提供的参考答案`；不得传入 `retrieved_contexts`、`reference_contexts` 或 \(R_q\)。
- 实现：Ragas `0.4.3` `RubricsScoreWithReference`；使用 `AsyncOpenAI` 客户端与 `llm_factory` 建立独立 Judge，调用 `await metric.ascore(...)`。
- 参数：读取 `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL`，`temperature=0`；默认只执行一次逻辑评分。
- 输出：从真实返回对象 `result.value` 读取 `raw_score`，范围 `1–5`；`normalized_score=(raw_score-1)/4`；`details={reason: result.reason}`；错误时 `details=null`。
- 边界：不读取来源 chunks，不参与评测数据集生成，也不调用其他 Ragas Metric。

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

同一 `metric_id` 的全部评测 case 必须聚合为一个 `MetricSummary`：

| 字段 | 契约 |
| --- | --- |
| `metric_id` | 对应 `metrics.json` 中的稳定 ID |
| `case_count` | 正式评测 case 总数 |
| `error_case_count` | `MetricResult.status=error` 的 case 数 |
| `mean_score` | 全部 case 的 `normalized_score` 等权算术平均；任一值为 `null` 时整体为 `null` |
| `status` | 任一 `MetricResult.status=error` 或 `normalized_score=null` 时为 `incomplete`；否则为 `completed` |

聚合只读取 `normalized_score`，不得读取 `raw_score` 判断完整性或计算均值；也不得按 Query 类型、chunk 数、Judge 调用次数或生成长度加权，或删除失败 case 后重算。MAP@5 与 MRR@5 分别使用 AP@5、RR@5 的全部 case 值按本节规则聚合。

## 9. 稳定错误码与处理责任

全部错误码使用小写点分命名空间；`code` 值稳定，人类可读 `message` 允许变化但必须脱敏。本节是分卷一与分卷三已确定评测运行错误码、选择优先级与处理边界的唯一事实来源；评测数据集生成的错误边界只由 `eval_set/` 规范定义。

### 9.1 Preflight

| 稳定 `code` | 触发条件 |
| --- | --- |
| `eval.preflight.metrics_config_missing` | `metrics.json` 不存在 |
| `eval.preflight.metrics_config_unreadable` | `metrics.json` 不可读或无法解析 |
| `eval.preflight.metrics_config_contract_invalid` | `metrics.json` 其他契约校验失败的兜底码 |
| `eval.preflight.metric_set_mismatch` | Metric 集合不是总卷固定的八项 |
| `eval.preflight.judge_config_invalid` | `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL` 或 `WS_RAG_JUDGE_MODEL` 缺失/空白；Base URL 不符合当前支持的火山方舟 HTTPS `/api/v3` 契约；`WS_RAG_MODEL_MAX_RETRIES` 无法解析或越界；或共享 Judge client 不能由这些已定义配置构造 |
| `eval.preflight.relevance_ground_truth_empty` | \(C_q\) 为空 |
| `eval.preflight.relevance_ground_truth_outside_corpus` | 任一 \(C_q\) 的 `chunk_id` 不属于当前 \(G_q\) |
| `eval.preflight.case_scoring_input_invalid` | case 不能提供声明的评分输入 |
| `eval.preflight.rag_entrypoint_unavailable` | 被测 RAG 运行入口不可用 |
| `eval.preflight.rag_index_unavailable` | 被测 RAG 所需索引不可用 |
| `eval.preflight.run_id_conflict` | 目标 `run_id` 会覆盖已有报告目录 |

Preflight 收集所有安全可评估错误，而非首错即停：配置无法成立时不执行依赖配置的 case 检查，RAG 入口不可用时不继续索引检查，`run_id` 冲突独立检查；不调用真实 RAG、Judge 或 Metric。Judge 配置只做本地构造性校验，不联网。汇总顺序固定为 metrics 文件错误、`metric_set_mismatch`、`judge_config_invalid`、`relevance_ground_truth_empty`、`relevance_ground_truth_outside_corpus`、`case_scoring_input_invalid`、RAG 入口、RAG 索引、`run_id` 冲突。每个 validator 对每个逻辑目标最多产生一次错误；汇总器不得按可变 `message` 进行事后去重。任一 preflight 错误都固定为：不创建正式 run，不调用 RAG 或任何 Metric，不写出报告。同一失败同时匹配专用码与 `*_contract_invalid` 兜底码时，必须选择专用码；Judge 配置失败同时匹配通用配置错误时，必须选择 `judge_config_invalid`。

### 9.2 Metric

| 稳定 `code` | 触发条件 |
| --- | --- |
| `eval.metric.retrieved_chunk_id_duplicate` | \(R_q\) 内 `chunk_id` 重复 |
| `eval.metric.input_invalid` | 未被专用码覆盖的单项 Metric 输入错误 |
| `eval.metric.dependency_call_failed` | Judge 或其他 Metric 依赖调用失败 |
| `eval.metric.dependency_response_parse_failed` | 依赖返回无法解析为本卷契约 |
| `eval.metric.score_out_of_range` | 返回分数超出契约范围 |
| `eval.metric.trulens_reason_missing` | TruLens `metadata` 缺少非空 `reason` |
| `eval.metric.accuracy_zero_denominator` | Accuracy 分母为 `0` |
| `eval.metric.accuracy_retrieved_chunk_outside_corpus` | \(R_q\) 出现不属于 \(G_q\) 的 `chunk_id` |

同一 Metric 失败同时匹配专用码和通用码时，必须选择专用码。`status=completed` 时 `errors=[]`；`status=error` 时 `errors` 恰好一个元素，并返回 `raw_score=null`、`normalized_score=null`、`details=null`。主错误选择优先级依次为专项输入错误、`eval.metric.input_invalid`、`eval.metric.dependency_call_failed`、`eval.metric.trulens_reason_missing`、`eval.metric.dependency_response_parse_failed`、`eval.metric.score_out_of_range`，以免同一根因被级联展开。分卷一继续其他 Metric 和后续 case；对应 `MetricSummary` 与 run 标记为 `incomplete`，两份报告仍必须写出。

### 9.3 Run 生命周期与非 Metric CLI

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

非 Metric 错误固定使用单行 stderr JSON envelope：顶层仅 `schema_version`、`status`、`run_id`、`errors`；其中 `errors[]` 每项仅 `code`、`message`。stdout 不得混入错误。退出码固定为：`0` 表示 run 为 `completed`；`1` 表示 preflight 失败、run 为 `incomplete` 或 `failed`；`2` 表示 argparse 参数或用法错误。

`run_status.json` 的位置、完整 schema、状态与错误字段约束只由[分卷一 §8.1](./2026-07-23-evaluation-optimization-loop-architecture-design.md#81-run_statusjson-契约)定义；本卷只提供其中 `code` 可选的稳定值域。

### 9.4 最小测试约束

- 每个已列 `code` 至少有一个可重复的触发用例，并断言对应阶段的固定动作。
- 同时匹配专用码与通用/兜底码时，测试必须断言只选择专用码。
- Preflight 测试必须断言其错误不进入 `MetricResult.errors`；Metric 错误测试必须断言 `completed` 的空 errors、`error` 的唯一主错误、统一空分数/空 details、继续调度、summary/run `incomplete` 与双报告写出。
- Preflight 测试必须覆盖依赖门禁、稳定多错误顺序与每目标一次。
- Run 测试必须覆盖三类 RAG/观测 fatal、聚合/构建/两类 writer fatal、状态记录一次重试和整目录发布；断言 fatal 优先于 `incomplete`、不伪造 MetricResult、不发布单份报告。CLI 测试必须断言 stderr 单行 envelope、stdout 无错误及三类退出码。
- 错误 `message` 测试必须确认不含密钥、完整请求/响应或错误堆栈。
- `run_status.json` 测试必须按分卷一 §8.1 断言位置、四个顶层字段、错误项双字段、状态特定 errors、目录内容与失败时 CLI 事实来源；不得从本卷新增字段或错误码。

## 10. 依赖与配置边界

- TruLens 项固定 `trulens-core==2.9.0` 与 `trulens-feedback==2.9.0`，通过 Fire provider 读取 Judge 配置。
- DeepEval 项固定 `deepeval==4.1.4`；任何 pytest、CI 或默认配置验证在 import 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。
- Ragas 项固定 `ragas==0.4.3`、`langchain-community==0.4.1` 与 `openai==2.30.0`；公开导入仅使用 `from ragas.llms import llm_factory` 与 `from ragas.metrics.collections import RubricsScoreWithReference`。
- Fire 评分代码不得直接导入 `DomainSpecificRubrics`、`ragas.evaluate`、LangChain wrapper 或任何 LangChain 类。

### 10.1 TruLens Fire provider

Fire 使用 `FireTruLensProvider` 从 `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL` 构造火山方舟 OpenAI-compatible client。v1 只支持 `.env.example` 所选的火山方舟普通 HTTPS `/api/v3` ChatCompletions 契约；这一收窄避免以“兼容”名义接受未经验证的服务方或接口形态。

| 请求/响应边界 | 固定契约 |
| --- | --- |
| 转发字段 | 只转发 `model`、`messages`、`stream=false` 与 `temperature=0`；温度仅允许值 `0` |
| `response_format` | 不发送给方舟；Fire 将 Pydantic JSON schema 作为纯格式约束追加到本次 `messages`/prompt，并在返回后本地 `model_validate` |
| `reasoning_effort` | 必须忽略，禁止进入最终方舟请求 |
| `thinking` | v1 不主动传入，沿用模型默认 |
| 其他 kwargs | 拒绝，避免依赖升级造成静默请求漂移 |
| 成功响应 | 只接受唯一 choice、非空 `message.content`，且 `finish_reason` 不能为 `length` |

Fire 不修改 TruLens 的评测语义 prompt、rubric、解析、评分或聚合；仅为本次 schema 追加纯格式约束。方舟调用异常、空 content 或 `finish_reason=length` 映射为 `eval.metric.dependency_call_failed`；JSON schema 或本地 Pydantic 校验失败映射为 `eval.metric.dependency_response_parse_failed`。这一边界让 transport 故障与评分语义保持分离。

### 10.2 DeepEval Judge adapter

`FireDeepEvalJudge` 继承 `DeepEvalBaseLLM`，显式读取 `WS_RAG_JUDGE_*` 并注入 `AnswerRelevancyMetric(model=...)`。它不得读取 `OPENAI_API_KEY`、使用 DeepEval 默认模型或依赖仓库 dotenv；pytest、CI 与默认配置验证仍须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。

| 边界 | 固定契约 |
| --- | --- |
| 方法形态 | 同步 `generate` 与异步 `a_generate` 都接受 `schema: BaseModel | None`；`a_generate` 必须是真正异步调用 |
| 请求字段 | 仅 `model`、单条 prompt message、`stream=false`、`temperature=0` |
| 禁止字段 | 不发送 `response_format`、`reasoning_effort` 或 `thinking` |
| 有 schema | 将 `schema.model_json_schema()` 作为纯格式约束追加到 prompt；解析 `message.content` 后用 `model_validate` 校验，并返回 schema 实例 |
| 无 schema | 只返回 `message.content` 字符串 |

该 adapter 仅解决 DeepEval 与 Fire Judge 的 transport/类型边界，不改变 Answer Relevancy 的评测语义 prompt、verdict、评分或聚合；仅追加 schema 纯格式约束。调用失败与返回空 content 映射 `eval.metric.dependency_call_failed`；JSON 或 schema 校验失败映射 `eval.metric.dependency_response_parse_failed`。

## 11. 实施验收

- 校验 `metrics.json` 恰好包含八项配置，且配置 hash 能检测 rubric 或参数变化。
- 验证系统 snapshot 在文件顺序、JSONL 记录顺序、对象 key 顺序或空白变化时保持不变，任一完整 chunk 对象内容变化时身份改变，且重复 `chunk_id` 在计算前被拒绝；`report.json` 保留系统 snapshot 的完整投影，`report.md` 只展示 `source_documents`。
- 验证 Precision/Recall 按本卷公式计分，名称不含 `@5`；\(R_q\) 仍是每 Query 最多 5 个 chunks 的最终有序结果，并非五个问题或五次运行。验证 AP@5 的分母固定为 `min(|C_q|,5)`。
- 验证 preflight 机械拒绝任一 \(C_q\) 超出 \(G_q\) 的 case，错误码为 `eval.preflight.relevance_ground_truth_outside_corpus`，且不创建正式 run、不调用网络。
- 验证 run 内 \(G_q\) snapshot 只在 preflight 首次读取 chunks 时建立；同一对象被 \(C_q \subseteq G_q\)、Accuracy 与 `report.json.system_snapshot` 使用，报告构建不得重新读取 chunks。
- 验证 Judge 三项配置缺失/空白、不支持的 Base URL、`WS_RAG_MODEL_MAX_RETRIES` 无法解析或越界、或共享 Judge client 不可构造时，preflight 不联网并以 `eval.preflight.judge_config_invalid` 拒绝 run。
- 使用精确 `WS_RAG_JUDGE_*` 配置分别完成真实 TruLens 与 DeepEval 调用，验证请求字段映射、结构化 schema、空/非法响应和失败路径；import 或 mock 不构成验收。
- 验证两个生成端 Metric 只接收非空 `answer_text=ChatResponse.conclusion.strip()`；不拼接或传递 `citations`、`scope`、`uncertainty`、`evidence`。
- 验证所有读取检索输出的 Metric 只消费最终融合后的有序 \(R_q\)，且没有融合前 chunks、融合前 rank、candidate IDs 或隐藏旁路；DeepEval 与 Ragas 不消费 \(R_q\)。
- 对每项 Metric 验证正常、空检索、重复 `chunk_id`、依赖异常和越界分数路径。
- 验证一个 case 的单项错误不会阻止后续 case 或其他 Metric 返回结果。
- 验证完成态与错误态的 `raw_score`、`normalized_score`、`details` 字段矩阵；正常 `raw_score=null` 不触发 `incomplete`，任一 `status=error` 或 `normalized_score=null` 都产生 `mean_score=null`、`status=incomplete`，且失败 case 不会被排除。
- 使用真实 Judge LLM 验证 TruLens `(normalized_score, metadata)`、DeepEval `metric.score/metric.reason` 与 Ragas `result.value/result.reason` 的接口映射和错误路径；公开 import smoke 不得代替真实调用验收。
