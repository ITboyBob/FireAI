# 分卷二：val_set 生成与冻结

> **文档类型**：专项架构设计分卷
> **日期**：2026-07-29
> **版本**：v2.0
> **状态**：Under Review

## 0. 卷册导航与本卷边界

- [返回设计总卷](../../新评测系统设计总卷.md)：确认当前只实施 evaluation，并按分卷导航继续读取。
- [分卷一：评测执行与报告架构](./2026-07-23-evaluation-optimization-loop-architecture-design.md)：读取正式 `val_set.json` 的消费方式。
- 当前分卷：独占“冻结 chunks → Ragas 候选 → 人工核验 → 完整 relevance ground truth → 正式 `val_set.json`”。
- [分卷三：Metric 与评分契约](./2026-07-27-ragas-response-reference-rubric-judge-design.md)：读取正式 val case 进入评分后的契约。

本卷只产生正式 `val_set.json`，不安排评测运行，也不定义评分配置、运行状态或输出文件。

## 1. 决策结论

本文设计 Ragas 的候选生成用途：基于仓库内全部冻结 chunks 生成单跳或多跳 Query 与参考答案候选。Ragas 返回候选后结束本次调用；随后由人工同时核验 Query、参考答案和全部来源 chunks。人工确认通过后才写入完整 relevance ground truth 并冻结正式 `val_set.json`；未通过时由人工选择重新生成或放弃。最终文件不保存审阅人、时间、状态或其他过程证据。

Ragas 行为与预计 import 面依据 [pre-chunked data 官方文档](https://docs.ragas.io/en/stable/howtos/customizations/testgenerator/prechunked_data/) 和 `0.4.3` 官方源码；`ragas==0.4.3` 与 `langchain-community==0.4.1` 已在项目依赖中固定。

## 2. 单一事实来源

本卷是 `val_set.json` 字段、生成、人工核验、稳定身份和发布规则的唯一事实来源。总卷与其他分卷只引用 `val_set_id`、`content_hash` 和 val case，不复制本卷的字段表或生成规则；描述冲突时以本卷为准。

## 3. 冻结输入边界

- 仓库内全部已有 chunks 构成唯一冻结输入集合。
- 接入采用 Ragas `Node` / `KnowledgeGraph` 路径：每个冻结 chunk 直接成为一个 CHUNK Node，Node 同时携带原文与稳定 `chunk_id`。
- 不重新读取整篇文章，不重新切分、合并或改写 chunk 文本，也不按 `document_id` 聚合。
- Ragas 可以提取属性、建立 chunk 关系，并在 scenario 层选择一个或多个 chunks；这些操作不得改变 chunk 的物理边界。
- 不读取或复用旧评测系统的 Dataset、Query 或字段。
- 禁止把已有 chunks 包装成 LangChain `Document` 输入；不得通过文本反查自建 `chunk_id` 映射。

## 4. 生成候选契约

每次 Ragas 生成都必须保存以下候选信息：

| 字段 | 含义 | Source |
| --- | --- | --- |
| `query` | Ragas 生成的自足 Query | Ragas `0.4.3` 生成结果 |
| `reference_answer` | 与 Query 同次生成的参考答案 | Ragas `0.4.3` 生成结果 |
| `generation_type` | 单跳或多跳 | Ragas `0.4.3` synthesizer 类型 |
| `source_chunk_ids` | 本次 scenario 实际使用的稳定 `chunk_id` | Fire 冻结 chunk 身份 |
| `generation_seq` | 初次生成批次中的稳定候选序号 | Fire 候选核验协议 |

`source_chunk_ids` 必须从 scenario 使用的 Node 属性直接读取，不能从 `reference_contexts` 文本反推；相同文本可以对应不同 `chunk_id`，必须保持不同身份。

## 5. Ragas 结束点与人工核验流程

```mermaid
flowchart LR
    F["冻结 chunks：chunk_id + 原文"] --> R["Ragas：单跳/多跳 scenario"]
    R --> C["候选：Query + 参考答案 + source_chunk_ids"]
    C --> E["Ragas 本次任务结束"]
    E --> H{"人工核验"}
    H -- "通过" --> V["写入完整 relevance ground truth"]
    H -- "重新生成" --> R
    H -- "放弃" --> X["不进入 val_set"]
    V --> P["冻结 val_set.json"]
```

人工核验失败后，程序只提供“重新生成”或“放弃”操作。只有人工点击“重新生成”时才再次调用 Ragas；不得由程序自动判定通过、自动调用 Judge 或自动循环重试。

## 6. 单跳人工核验

人工必须同时查看 Query、参考答案和唯一来源 chunk，并确认该 chunk 单独包含参考答案所需的全部事实。通过后，该来源 chunk 成为该 Query 正式、完整的 relevance ground truth；若 chunk 不能单独支持答案、Query 需要外部信息或参考答案包含原文没有的事实，则选择重新生成或放弃。

## 7. 多跳人工核验

人工必须同时查看 Query、参考答案和全部来源 chunks，确认这些 chunks 合并后能够完整回答 Query，并确认每个 chunk 都提供参考答案所需的具体事实。任一 chunk 没有提供所需事实，候选即不通过；人工只能选择重新生成或放弃。

对 Query \(q\)，人工核验通过的全部来源 chunk 集合记为 \(G_q\)。\(G_q\) 是该 Query 正式、完整的 relevance ground truth，并随 val case 一起冻结；下游只能读取，不得补写或改写。

## 8. Ragas 默认生成配置

除适配层映射的 Ragas SDK `testset_size` API 参数外，Ragas `0.4.3` 已提供默认值的生成参数均采用上游默认，不另行自定义：

| 配置项 | 已确定值 | Source |
| --- | --- | --- |
| pre-chunked transforms | `generate_with_chunks` 对应的默认 transforms | Ragas `0.4.3` pre-chunked 实现 |
| query distribution | 可用的 `SingleHopSpecificQuerySynthesizer`、`MultiHopAbstractQuerySynthesizer`、`MultiHopSpecificQuerySynthesizer` 等权 | Ragas `0.4.3` 默认 query distribution |
| persona 数量 | `num_personas=3` | Ragas `0.4.3` 默认参数 |
| 批处理与执行 | `batch_size=None`、`return_executor=False` | Ragas `0.4.3` 默认参数 |
| 调试与异常 | `with_debugging_logs=False`、`raise_exceptions=True` | Ragas `0.4.3` 默认参数 |
| `RunConfig` | `timeout=180`、`max_retries=10`、`max_wait=60`、`max_workers=16`、`log_tenacity=False`、`seed=42` | Ragas `0.4.3` 默认参数 |
| `llm_factory` 模型参数 | `temperature=0.01`、`top_p=0.1`、`max_tokens=1024` | Ragas `0.4.3` 默认参数 |
| Query 风格与长度 | 沿用各 synthesizer 上游默认 | Ragas `0.4.3` synthesizer 默认 |

Fire 业务与 JSON 契约使用 `val_set_case_count=6` 表示最终经人工核验通过并冻结的 case 数，使用 `preliminary_case_count=9` 表示初次生成的候选数。Ragas SDK 的 `testset_size` 不是 Fire 字段；适配层只在外部 API 调用时传入 `testset_size=preliminary_case_count`。超采样余量不设置字段，机械计算为 `preliminary_case_count-val_set_case_count=3`。禁止继续使用旧业务字段名。生成模型连接复用旧评测 LLM generator 的 `.env.example` 配置：`WS_RAG_QUESTION_GENERATOR_API_KEY`、`WS_RAG_QUESTION_GENERATOR_BASE_URL`、`WS_RAG_QUESTION_GENERATOR_MODEL`；不得误用 `CHAT_*` 或 Judge 配置。

## 9. `chunk_id` 传递方案

已选择 Ragas `Node` / `KnowledgeGraph` 方案，流程固定为：

1. 读取冻结 chunks，为每个 chunk 构造类型为 CHUNK 的 Ragas Node，并把原文与稳定 `chunk_id` 写入 Node 属性。
2. 用这些 Nodes 组装 `KnowledgeGraph`，应用 Ragas `0.4.3` pre-chunked 默认 transforms。
3. `TestsetGenerator` 基于该图生成 scenario、Query 与参考答案候选。
4. 在 scenario 节点仍可访问时，从节点属性读取 `chunk_id`，写入 `source_chunk_ids`。

**Rejected alternative — LangChain `Document.metadata`**：不采用。该方案需要把已有 chunks 二次包装为 LangChain `Document`，扩大 Fire 对 LangChain 业务 API 的直接耦合，且 metadata 是否全程保留仍需真实调用证明；Node 方案能在 Ragas 自身身份模型内直接携带 `chunk_id`。文本反查映射同样禁止，因为相同文本可能属于不同 chunks。

## 10. `val_set.json` 冻结契约

默认只生成一份 `val_set.json`，初始 `schema_version` 为 `1.0.0`。内容范围参考上游 evaluation quickstart 的“测什么”，不继承其字段名、SDK、Agent 会话或工具轨迹。

| 层级 | 字段 | 已确定含义 | Source |
| --- | --- | --- | --- |
| 顶层 | `schema_version` | 初始固定为 `1.0.0` | 用户决策；机械生成 |
| 顶层 | `val_set_id` | `val_<content_hash digest 前12位>`，不人工命名 | 用户决策；仓库 canonical JSON 与 `doc_<12hex>` 身份先例 |
| 顶层 | `frozen_at` | 冻结时间 | 用户决策；机械生成 |
| 顶层 | `content_hash` | 对规范化 `cases` 内容计算的集合哈希 | 用户决策；机械生成 |
| 顶层 | `val_set_case_count` | 固定为 `6`；最终人工通过并冻结的 case 数 | 用户决策 |
| 顶层 | `preliminary_case_count` | 固定为 `9`；初次生成的候选数 | 用户决策 |
| 顶层 | `cases` | 冻结 case 数组 | 用户决策；上游模板内容范围 |
| case | `case_id` | 从该 case 规范化内容哈希机械生成的稳定 ID | 用户决策；机械生成 |
| case | `query` | 人工核验通过的 Query | 用户决策 |
| case | `reference_answer` | 人工核验通过的参考答案 | 用户决策 |
| case | `generation_type` | 单跳或多跳 | Ragas 生成结果 |
| case | `relevance_ground_truth` | 完整 ground truth 的 chunk 快照数组；每项至少保存稳定 `chunk_id` 与原文 `text`；同一数组内 `chunk_id` 唯一，且 \(G_q\) 是冻结 chunks 的子集 | 用户决策 |

不得写入 `review_status`、审阅人、审阅时间、审阅记录或其他人工核验证据字段。

`val_set_id` 与 `content_hash` 按既有稳定身份规范机械生成：

1. 从待冻结 payload 排除 `val_set_id`、`content_hash`/`fingerprint`、`frozen_at` 等派生或易变字段。
2. 使用 UTF-8、key 排序、紧凑分隔符和不转义非 ASCII 字符的 canonical JSON。
3. 对 canonical payload 计算 SHA-256；完整值保存为 `content_hash=sha256:<64hex>`。
4. 使用同一 digest 前 12 位生成 `val_set_id=val_<12hex>`。

该规则沿用 [`scripts/eval_ws_rag/dataset_models.py`](../../scripts/eval_ws_rag/dataset_models.py) 的 canonical JSON/SHA-256 fingerprint 规范，并沿用 [`app/services/corpus_ingestor.py`](../../app/services/corpus_ingestor.py) 的 `<类型前缀>_<digest前12位>` 稳定 ID 形态；不增加 namespace、release、revision 或用途 alias。

## 11. 候选计数与文件一致性

- 候选按 `generation_seq` 稳定顺序核验；达到 `val_set_case_count=6` 后，冻结顺序最靠前的 6 个通过 case。
- 放弃的 case 不计入通过数；使用尚未核验的候选继续补足。达到目标后仍未核验的多余候选不得进入 `val_set.json`。
- 初次 9 条候选不足以得到 6 条人工通过的 case 时，沿用补足规则继续生成候选；补充生成不改变 `preliminary_case_count=9` 的“初次候选数”语义。
- 冻结 chunks 为空时 hard fail，且不得创建、截断或替换正式文件。
- `chunk_id` 重复时 hard fail；相同文本但 `chunk_id` 不同是合法输入，保持不同 Node 身份。
- Ragas 生成失败时不发布部分结果，并保留旧 `val_set.json` 不变。
- 只在临时产物通过 schema、稳定 ID、内容 hash 和 `len(cases) == val_set_case_count` 校验后，原子替换正式 `val_set.json`；不得保留含义重复的顶层 `case_count`。
- 最终文件不保存任何人工审阅证据。

## 12. 依赖、embedding 与 import 边界

候选生成固定使用 `ragas==0.4.3` 与 `langchain-community==0.4.1`。Fire 只通过 Ragas 的公开接口构造候选生成链，不在业务代码中导入 LangChain 类型：

- `ragas.testset.synthesizers.generate.TestsetGenerator`
- Ragas `Node` 与 `KnowledgeGraph` 的 `0.4.3` 公开导出
- `ragas.llms.llm_factory`
- `ragas.embeddings.HuggingFaceEmbeddings`
- `ragas.testset.synthesizers.SingleHopSpecificQuerySynthesizer`
- `ragas.testset.synthesizers.MultiHopAbstractQuerySynthesizer`
- `ragas.testset.synthesizers.MultiHopSpecificQuerySynthesizer`

Ragas embedding 必须与现有检索 embedding 保持同一配置语义：

- `model` 取当前 `EMBEDDING_MODEL_NAME`。
- `device`、`batch_size` 取现有 `Settings` 对应值。
- `normalize_embeddings=True`，不得改用未归一化向量。
- `max_seq_length` 非空时，必须应用到 `HuggingFaceEmbeddings` 持有的底层 `SentenceTransformer`；具体属性路径随最终固定的 Ragas 版本在实施时验证。
- 不得改用其他 embedding 实现，也不得为 Ragas 另选 embedding 模型或另建一套配置。

Node 方案不能消除 Ragas 的传递依赖，但不得因此把 LangChain `Document`、loader、splitter 或其他 LangChain 业务接口带入本模块。当前只验证了公开 import、Node/KnowledgeGraph 的 `chunk_id` 往返与 API 形状；真实候选生成和人工核验后的正式文件发布仍待实施验证。

## 13. 后续实施验收

- 验证 Ragas `0.4.3` Node/KnowledgeGraph 链能在真实候选生成中完整保留稳定 `chunk_id`。
- 执行真实候选生成，确认 Query、参考答案与 `source_chunk_ids` 能进入人工核验。
- 通过单跳、多跳、重新生成、放弃与补足场景，确认只冻结人工通过的 6 个 case。
- 验证 schema、稳定 ID、内容 hash 与原子替换；失败时旧 `val_set.json` 保持不变。
