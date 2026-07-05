# Word/W 单文件 RAG 问答评测实施计划：分卷二

> 本分卷负责真实 RAG、Judge、规则校验、聚合和 run 目录级原子报告。

## 1. 分卷入口检查

### 已确认

- 分卷一已提供共享报告 schema 和不可变 dataset；
- 当前真实链路入口是 `Retriever.search()` 与 `build_answer()`；
- 当前在线 `OpenAIChatClient` 固定验证 `ModelAnswer`，Judge 必须使用独立结构化响应适配器；
- 正式报告由 `report.json`、`errors.json` 组成，Dashboard 只读取完成发布的 run 目录。

### 缺失输入

- 分卷一产出的 `dataset_id` 和 `dataset_fingerprint`。

### 默认值

- 检索 `top_k=5`，保留 Retriever 原始排序；
- Judge 重复 3 次，run seed 控制证据顺序；
- 答案生成读取现有 `CHAT_*`；Judge 读取 `WS_RAG_JUDGE_*`，模型为 `doubao-seed-2-1-pro-260628`、温度为 `0`；
- 答案生成与 Judge 串行执行，临时失败后最多额外重试 1 次；
- 致命错误只写 `var/ws_rag_eval/<run_id>/debug.json`，不发布正式 run；
- 无需新增依赖，全部使用 conda 环境 `fire`。

## 2. Phase 3：真实 RAG 与独立 Judge

### Task 5：实现真实 RAG Runner

**阶段输入检查：**

- 已确认：dataset 已固化且真实索引存在；
- 缺失：无用户侧关键缺失；正式运行只验证现有 `CHAT_*` 可用；
- 默认：Runner 不过滤跨文档召回，由后续规则显式判定；每题答案生成严格串行。

**依赖与包管理：** 后端使用 conda 环境 `fire`，复用现有 FAISS、OpenAI SDK 和服务代码，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/rag_runner.py`
- 新建：`tests/eval_ws_rag/test_rag_runner.py`
- 修改：`tests/eval_ws_rag/fixtures/valid_report.json`

**Step 1：先写失败测试。**

覆盖：

- 每题调用一次 `retriever.search(question, top_k=...)`；
- 原始 top-k 顺序、score、chunk ID、document ID 原样记录；
- 同一原始 evidence 传给 `build_answer()`；
- 空召回正常进入拒答，不伪造成检索错误；
- query normalization、keyword、vector encoding/search、fusion 异常带阶段标识；
- 索引缺失和融合异常为致命错误，单题格式异常可恢复。
- 答案模型配置只读取现有 `CHAT_*`，不接受 CLI 模型覆盖；
- 临时模型错误只额外重试 1 次，当前题完成前不得开始下一题。

**Step 2：确认预期失败。**

**命令执行意图：** 证明 Runner 尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rag_runner.py -q
```

**预期输出：** FAIL，原因是 `rag_runner` 或目标类型不存在。

**Step 3：最小实现。**

实现 `RagRunResult`、`RagStageError` 和 `run_question()`。Runner 接收已构造的 Retriever 与答案 client，不在模块内读取环境变量；调用链固定为规范化问题 → 真实检索 → `build_answer()` → 结构化结果。

Runner 必须分别保留：

- `retrieved_chunks`：真实 top-k 完整快照，每项含 chunk/document ID、path、text、retrieval score 和后续可回填的 `cited`；
- `answer`、原始 citations、`refused`、`uncertainty`；
- 当前目标 `document_id`；
- 生成模型名和耗时，不记录 API Key。

**Step 4：通过测试。**

**命令执行意图：** 验证真实服务调用边界和错误分类。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rag_runner.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

使用真实 `data/index/` 和 fake answer client，避免模型波动；Retriever 必须是真实实例。

**命令执行意图：** 验证真实关键词/向量索引可返回目标条文。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rag_runner.py -q -k real_index
```

**预期输出：** PASS，无 skip；结果包含真实 chunk ID 和 document ID。

**Checkpoint：** 真实检索排序未被评测脚本改写，错误阶段可追踪。

**中文 commit：** `feat(eval): 接入真实RAG评测执行器`

### Task 6：实现独立结构化 Judge 与评分协议

**阶段输入检查：**

- 已确认：Judge 与答案生成必须解耦，且要对冲位置偏见；
- 缺失：无用户侧关键缺失；正式运行前验证 Judge 环境变量和 provider 能力；
- 默认：模型 `doubao-seed-2-1-pro-260628`、重复 3 次、温度 0、证据顺序按 `seed + question_id + repetition` 稳定打乱。

**依赖与包管理：** 后端使用 conda 环境 `fire` 与现有 OpenAI SDK/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/eval_chat_client.py`
- 新建：`scripts/eval_ws_rag/llm_judge.py`
- 新建：`tests/eval_ws_rag/test_eval_chat_client.py`
- 新建：`tests/eval_ws_rag/test_llm_judge.py`
- 修改：`docs/reference_material/2026-07-05-ws-rag-evaluation-runtime-contract-verification.md`

**Step 0：实现前核验 OpenAI Structured Outputs 官方契约。**

只使用 OpenAI 官方 Structured Outputs 与当前 Python SDK 文档，并按仓库联网规则通过 Firecrawl、Exa 或 Tavily 获取；核对 `response_format`/结构化解析入口、JSON Schema 支持范围、严格模式、错误类型、超时和重试语义。

**命令执行意图：** 读取 `fire` 环境实际 OpenAI SDK 版本。

```bash
conda run -n fire python -c "import openai; print(openai.__version__)"
```

**预期输出：** 一个已安装的 OpenAI Python SDK 精确版本。

把核验日期、SDK 版本、官方 URL、目标 provider 能力和结论追加到运行时契约核验记录。若目标 provider 或当前 SDK 不兼容本计划要求的 JSON Schema/严格结构化输出，立即停止 Task 6 并向用户给出差异与备选方案；未经用户批准不得自动降级为文本 JSON。

**Step 1：先写失败测试。**

覆盖：

- 自定义 response schema，而不是在线 `ModelAnswer`；
- context chunk 逐项 `helpful`；
- answer 拆 claim 后逐项 `supported/not_supported/unknown`；
- 答案相关性为 1～5 并归一化到 `[0,1]`；
- 三次 evidence 顺序不同但可由 seed 复现；
- 聚合取算术平均，保留每次原始判定；
- prompt 明确忽略长度，Judge 输入不暴露被测版本名；
- 429/临时错误最多额外重试 1 次，第二次失败抛 run 级致命错误；
- 三次 Judge 重复评分逐次串行，任一问题完成前不得开始下一问题；
- schema 非法、缺字段、越界分数立即失败。

**Step 2：确认预期失败。**

**命令执行意图：** 证明独立 Judge 客户端和评分器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_eval_chat_client.py tests/eval_ws_rag/test_llm_judge.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

- `StructuredEvalClient.complete(messages, response_model)` 复用 OpenAI SDK，从 `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL`、`WS_RAG_JUDGE_TEMPERATURE` 读取配置；
- 不 import 或调用在线 `_build_response_format()`；
- `JudgeResult` 保存三项 LLM 指标、claim/context 明细、重复次数和 prompt version；
- Judge 配置显式传入，不读取答案生成模型名作为默认值；
- `WS_RAG_MODEL_MAX_RETRIES` 默认并固定验收值为 `1`；所有模型调用串行；
- 不提供默认文本 JSON fallback；provider 不支持本计划的严格结构化输出时按 Step 0 停止。

**Step 4：通过测试。**

**命令执行意图：** 验证 Judge 协议、偏见对冲和错误策略。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_eval_chat_client.py tests/eval_ws_rag/test_llm_judge.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

使用真实 RAG fixture 但 fake Judge client，验证长短答案不影响协议字段、证据乱序可复现。

**命令执行意图：** 验证 Judge 可处理真实 chunk 形状。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_llm_judge.py -q -k real_chunk_shape
```

**预期输出：** PASS，未进行外部模型调用。

**Checkpoint：** Judge schema、模型配置、prompt 版本和重复评分均可审计。

**中文 commit：** `feat(eval): 实现独立结构化Judge`

## 3. Phase 4：规则、聚合与原子发布

### Task 7：实现规则校验和问题通过判定

**阶段输入检查：**

- 已确认：红线包括无效引文、文件外无依据内容、该拒答时不拒答；
- 缺失：无；
- 默认：任何红线失败都令问题 `passed=false`。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/rule_validator.py`
- 新建：`tests/eval_ws_rag/test_rule_validator.py`

**Step 1：先写失败测试。**

覆盖：

- citations 必须能逐字绑定 retrieved evidence；
- `source_coverage` 依据 dataset 的 `expected_article` 与召回 chunk 判定；
- 可回答问题拒答、不可回答问题未拒答均失败；
- 回答包含当前文件外且无证据支持的内容时记录稳定红线代码 `out_of_scope_content`；
- 另外两种红线代码固定为 `citation_invalid`、`missing_required_refusal`，不得以页面中文文案充当程序条件；
- 无引文时 citation validity 的分母规则明确：需引文的可回答题为 `0`，正确拒答题为 `1`；
- 六项阈值同时通过且无红线才 `passed=true`；
- failure reason 使用稳定机器码和中文说明。

**Step 2：确认预期失败。**

**命令执行意图：** 证明规则校验器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rule_validator.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

实现 `validate_rules()` 与 `decide_question_pass()`。本地规则不调用 LLM；“文件外无依据内容”的语义 claim 由 Judge 明细输入，文档 ID 和引文绑定由本地程序复核。校验器把原始引文规范化为结构化 `CitationRecord`，至少含 `document_id`、`path`、`text`、`matched_chunk_id`，并回填对应 retrieved chunk 的 `cited`。

**Step 4：通过测试。**

**命令执行意图：** 验证红线、阈值和拒答判定。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rule_validator.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

**命令执行意图：** 使用真实 chunk ID、条号和 document ID 验证引文绑定。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rule_validator.py -q -k real_chunk
```

**预期输出：** PASS，跨文档 evidence 被显式记录而非静默删除。

**Checkpoint：** 红线、质量指标和通过判定只有一套机器规则。

**中文 commit：** `feat(eval): 实现评测规则与红线门禁`

### Task 8：实现聚合器和报告一致性校验

**阶段输入检查：**

- 已确认：问题级→文件级→run 级聚合公式已冻结；
- 缺失：无；
- 默认：均值使用未四舍五入原值计算，仅序列化显示值可限制小数位。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/report_aggregator.py`
- 新建：`tests/eval_ws_rag/test_report_aggregator.py`

**Step 1：先写失败测试。**

覆盖六项算术平均、问题/失败/红线计数、零问题拒绝、跨文档加权总体通过率、稳定排序、嵌套 `dataset`/`protocol`/`system` 透传、`protocol_fingerprint` 和报告模型二次校验。

**Step 2：确认预期失败。**

**命令执行意图：** 证明聚合器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_aggregator.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

实现 `aggregate_document()` 与 `aggregate_run()`；run 总通过率必须以通过问题数/总问题数计算，不能对文件通过率再求平均。

**Step 4：通过测试。**

**命令执行意图：** 验证聚合公式与共享 schema。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_aggregator.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

**命令执行意图：** 对带 W-S1/W-S2 真实标识的 fixture 聚合并重载。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_aggregator.py -q -k ws_fixture
```

**预期输出：** PASS，聚合值与手工期望一致。

**Checkpoint：** Dashboard 所需所有字段由共享模型生成并通过一致性校验。

**中文 commit：** `feat(eval): 实现评分卡与报告聚合`

### Task 9：实现 run 目录级暂存和原子发布

**阶段输入检查：**

- 已确认：两个正式 JSON 不能先后独立暴露；
- 缺失：无；
- 默认：暂存目录为同一父目录下 `.<run_id>.tmp-<uuid>`，确保目录重命名位于同一文件系统。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/report_publisher.py`
- 新建：`tests/eval_ws_rag/test_report_publisher.py`
- 修改：`docs/reference_material/2026-07-05-ws-rag-evaluation-runtime-contract-verification.md`

**Step 0：实现前核验 Python 3.14 文件系统语义。**

只使用 Python 3.14 官方 `os.rename()`、`os.fsync()` 和文件/目录操作文档，并按仓库联网规则通过 Firecrawl、Exa 或 Tavily 获取；核对同文件系统目录重命名、目标已存在行为、父目录 fsync 可用性和当前 macOS 语义。

**命令执行意图：** 确认 `fire` 环境 Python 精确版本。

```bash
conda run -n fire python -c "import sys; print(sys.version)"
```

**预期输出：** Python 3.14.x。

把核验日期、Python/macOS 版本、官方 URL、可依赖语义和限制追加到运行时契约核验记录。若无法证明“正式目录不覆盖 + 整目录一次可见”，停止 Task 9，不以逐文件 rename 冒充 run 级原子发布。

**Step 1：先写失败测试。**

覆盖：

- 先创建 run 暂存目录，再写两个 `.tmp` 文件；
- 文件 flush/fsync 后改名为暂存目录内正式文件；
- 从磁盘重新读取并用共享 schema 交叉校验；
- 在父目录发布锁内确认目标不存在，最后一次目录重命名发布整个 run；
- 任一步失败时正式目录不存在，暂存目录清理；
- 同名正式 run 拒绝覆盖；
- report/errors 头部不一致拒绝；
- 模拟第二文件写入失败时 Dashboard 根目录没有半成品 run。

**Step 2：确认预期失败。**

**命令执行意图：** 证明目录级发布器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_publisher.py -q
```

**预期输出：** FAIL，原因是目标发布器不存在。

**Step 3：最小实现。**

实现 `publish_run_atomic(report, errors, reports_root)`；正式目录只包含 `report.json` 与 `errors.json`。发布器使用父目录独占锁串行化协作进程，在锁内再次检查目标不存在，以 `os.rename(staging_dir, final_run_dir)` 一次发布并 fsync 父目录；不可恢复异常由上层写入 `var/`，发布器不生成失败 run。

**Step 4：通过测试。**

**命令执行意图：** 验证成对报告的目录级原子可见性。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_publisher.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实文件系统验证。**

**命令执行意图：** 在 pytest 临时目录模拟完整发布和中途失败。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_publisher.py -q -k filesystem
```

**预期输出：** PASS；成功时一次出现完整 run，失败时无正式目录和残留暂存目录。

**Checkpoint：** Dashboard 永远不会看到仅含一个 JSON 的已发布 run。

**中文 commit：** `feat(eval): 实现评测报告目录级原子发布`

## 4. 分卷二完成门禁

**命令执行意图：** 执行分卷二全部测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_rag_runner.py tests/eval_ws_rag/test_eval_chat_client.py tests/eval_ws_rag/test_llm_judge.py tests/eval_ws_rag/test_rule_validator.py tests/eval_ws_rag/test_report_aggregator.py tests/eval_ws_rag/test_report_publisher.py -q
```

**预期输出：** 全部 PASS，无新增 skip/xfail；真实索引验证已执行。

进入分卷三前必须能在临时目录原子发布一对通过共享 schema 的报告。
