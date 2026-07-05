# Word/W 单文件 RAG 问答评测实施计划：分卷一

> 本分卷负责共享契约、不可变问题集和问题生成，不执行真实评测。

## 1. 分卷入口检查

### 已确认

- 主设计定义六个指标、三类问题和单文件评分卡；
- Dashboard 首轮用共享 schema 的单个 mock `report.json` / `errors.json`，未来真实接入仍复用同一契约；
- `data/chunks/*.jsonl` 已包含 `document_id`、`title`、`path`、`text`、`article_no`、`source_sha256`、`extraction_class`、`content_class`；
- `openai`、Pydantic、pytest 已在 `pyproject.toml`，无需新增依赖。

### 缺失输入

- 无用户侧关键缺失；阶段开始时只需验证已确认环境变量可读取且密钥不进入日志。

### 默认值

- dataset 根目录 `data/eval/ws_rag_datasets/`；
- 问题类型固定为 `frequent`、`boundary`、`diversity`；
- 目标文档固定为 W-S1 `doc_d97773f1500c` 和 W-S2 `doc_0e84d13a099b`；
- 三类问题数量分别读取 `WS_RAG_FREQUENT_QUESTIONS_PER_DOCUMENT`、`WS_RAG_BOUNDARY_QUESTIONS_PER_DOCUMENT`、`WS_RAG_DIVERSITY_QUESTIONS_PER_DOCUMENT`，默认均为 `1`；
- 问题生成模型读取 `WS_RAG_QUESTION_GENERATOR_API_KEY`、`WS_RAG_QUESTION_GENERATOR_BASE_URL`、`WS_RAG_QUESTION_GENERATOR_MODEL`，模型默认 `deepseek-v4-pro-260425`；
- 问题生成串行执行，失败后最多额外重试 1 次；
- 可回答问题必须有 `expected_article`，不可回答问题必须声明 `expected_behavior=refuse`；
- 所有 Python 命令使用 conda 环境 `fire`。

## 2. Phase 1：共享契约与不可变 dataset

### Task 1：建立共享报告 schema 与配置

**阶段输入检查：**

- 已确认：主设计六项阈值和 Dashboard 顶层结构；
- 缺失：无关键缺失，可使用总览默认阈值；
- 默认：`schema_version=1.0.0`，时间统一为带时区 ISO 8601。

**依赖与包管理：** 后端使用 conda 环境 `fire` 与现有 Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/__init__.py`
- 新建：`scripts/eval_ws_rag/report_models.py`
- 新建：`scripts/eval_ws_rag/config.json`
- 新建：`tests/eval_ws_rag/test_report_models.py`
- 新建：`tests/eval_ws_rag/fixtures/valid_report.json`
- 新建：`tests/eval_ws_rag/fixtures/valid_errors.json`
- 新建：`docs/reference_material/2026-07-05-ws-rag-evaluation-runtime-contract-verification.md`

**Step 0：实现前核验 Pydantic v2 官方契约。**

只使用 Pydantic 官方 `Models`、`Validators` 文档，并按仓库联网规则通过 Firecrawl、Exa 或 Tavily 获取；不得以博客或记忆替代。核对当前 v2 版本的 `BaseModel`、`model_validate()`、field/model validator、严格模式和额外字段策略。

**命令执行意图：** 读取 `fire` 环境实际 Pydantic 版本。

```bash
conda run -n fire python -c "import pydantic; print(pydantic.__version__)"
```

**预期输出：** 一个已安装的 Pydantic v2 精确版本。

把核验日期、精确版本、官方 URL、适用 API、结论和与计划的差异写入运行时契约核验记录；结论不明确时停止 Task 1。

**Step 1：先写失败测试。**

测试必须固定：

- 六项 score 均在 `[0, 1]`；
- `summary.question_count` 等于所有文档问题数；
- 顶层 `dataset`、`protocol`、`system` 为必填；分别承载固定问题集身份、评测口径和被测系统身份；
- `dataset.dataset_id`、`dataset.dataset_fingerprint`、`protocol.protocol_fingerprint`、Judge/生成模型精确版本及各自 prompt 版本为必填；
- `protocol.judge_calibrated` 为必填，首轮固定为 `false`；
- `protocol_fingerprint` 必须覆盖 Judge 精确模型、Judge prompt 版本、重复次数、证据顺序策略、指标算法版本和全部阈值；
- `summary` 的问题/通过/失败/红线计数必须与 `documents[].questions[]` 一致；
- report 与 errors 的 `schema_version`、`run_id`、`created_at` 必须一致；
- 未知主版本或未声明支持的 minor 版本拒绝加载；
- Dashboard 允许的展示字段均来自这些模型。

`EvaluationError` 至少包含 `document_id`、`question_id`、`stage`、`stage_description`、`error_type`、`message`、`recoverable` 和脱敏 `input_snapshot`；完整 traceback 只进入 `var/` 调试记录。

**Step 2：确认预期失败。**

**命令执行意图：** 证明共享模型尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_models.py -q
```

**预期输出：** FAIL，原因是 `scripts.eval_ws_rag.report_models` 或目标模型不存在。

**Step 3：最小实现。**

至少实现 `EvaluationReport`、`ErrorReport`、`DatasetIdentity`、`EvaluationProtocol`、`EvaluatedSystem`、`DocumentScorecard`、`QuestionResult`、`RetrievedChunk`、`CitationRecord`、`MetricScores`、`FailureReason`、`EvaluationError`。配置默认阈值必须与主设计一致，不得从 Dashboard 复制另一套常量。

共享规则：

- 主评测写入前调用 `model_validate()`；
- Dashboard loader 直接 import 这些模型；
- 若 Dashboard 需要只读兼容旧 schema，应在这里提供显式版本适配，不复制模型。

**Step 4：通过测试。**

**命令执行意图：** 验证共享 schema 和配置约束。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_models.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

**命令执行意图：** 确认报告模型可导入且默认阈值正确。

```bash
conda run -n fire python -c "from scripts.eval_ws_rag.report_models import EvaluationProtocol; print(EvaluationProtocol.default_thresholds())"
```

**预期输出：** 显示 `0.8/0.9/0.9/0.8/1.0/0.9` 六项阈值，不读取或修改真实数据。

**Checkpoint：** 两个合法 fixture 可 round-trip，非法聚合和版本均失败。

**中文 commit：** `feat(eval): 建立评测报告共享契约`

### Task 2：建立不可变 dataset 模型与指纹

**阶段输入检查：**

- 已确认：问题生成必须与评测执行分离；
- 缺失：无；
- 默认：规范化 JSON 采用 UTF-8、键排序、紧凑分隔符，指纹使用 SHA-256。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/dataset_models.py`
- 新建：`scripts/eval_ws_rag/dataset_store.py`
- 新建：`tests/eval_ws_rag/test_dataset_store.py`

**Step 1：先写失败测试。**

覆盖：

- 相同语义内容即使字典键顺序不同也得到相同 fingerprint；
- `created_at` 不参与 fingerprint；
- 问题文本、来源 chunk、期望条文、期望行为或来源摘要变化都会改变 fingerprint；
- dataset 目录已存在时拒绝覆盖；
- 读取时重新计算指纹，不一致立即失败。

`EvaluationDataset` 至少包含：

- `schema_version`、`dataset_id`、`dataset_fingerprint`、`created_at`；
- `generator_model`、`generator_prompt_version`、`generation_seed`；
- `documents[]` 中每份文档的 `document_id`、`source_sha256`、`content_class`；
- 各文档 `questions[]` 中的 `question_id`、`question`、`question_type`、`answerable`、`expected_behavior`、`expected_article`、`source_chunk_id`、`answer_sketch`。

**Step 2：确认预期失败。**

**命令执行意图：** 证明 dataset 存储与指纹函数尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dataset_store.py -q
```

**预期输出：** FAIL，原因是目标模块或函数不存在。

**Step 3：最小实现。**

实现 `canonical_dataset_payload()`、`compute_dataset_fingerprint()`、`save_dataset_atomic()`、`load_dataset()`。写入流程为父目录下创建临时 dataset 目录 → 写入临时文件并 flush/fsync → 临时文件改为 `dataset.json` → 临时目录一次重命名为正式 dataset 目录；正式目录已存在时失败，禁止覆盖。

**Step 4：通过测试。**

**命令执行意图：** 验证 dataset 不可变性和指纹。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dataset_store.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

使用临时目录和一条真实 chunk 构造 dataset，不调用模型、不写正式 `data/eval/`。

**命令执行意图：** 用真实 chunk 字段验证模型兼容性。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dataset_store.py -q -k real_chunk
```

**预期输出：** PASS，且临时 dataset 重载后的 fingerprint 不变。

**Checkpoint：** dataset 双标识可持久化、可复算、不可覆盖。

**中文 commit：** `feat(eval): 固化不可变评测问题集`

## 3. Phase 2：文档加载与独立问题生成

### Task 3：只读加载单文件 chunks 并固定来源

**阶段输入检查：**

- 已确认：真实 chunks 字段已存在；
- 缺失：目标 `document_id` 由 CLI 参数提供；
- 默认：只接受 `extraction_class=W` 且 `content_class` 为 `S1` 或 `S2`。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/document_loader.py`
- 新建：`tests/eval_ws_rag/test_document_loader.py`

**Step 1：先写失败测试。**

覆盖单一 `document_id`、一致 `source_sha256`、稳定 chunk 顺序、空文件、JSON 损坏、混入第二文档、非 W/S1-S2 拒绝。

**Step 2：确认预期失败。**

**命令执行意图：** 证明只读加载器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_document_loader.py -q
```

**预期输出：** FAIL，原因是目标加载器不存在。

**Step 3：最小实现。**

实现 `load_document_chunks(chunks_dir, document_id)`，只读 `data/chunks/<document_id>.jsonl`，按 `article_index/chunk_index` 稳定排序并返回来源元信息；禁止修改 chunks。

**Step 4：通过测试。**

**命令执行意图：** 验证加载与来源门禁。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_document_loader.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

**命令执行意图：** 从正式 chunks 读取一个 W-S1 和一个 W-S2 文档。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_document_loader.py -q -k real_ws
```

**预期输出：** 两个真实样本 PASS，无 skip，源文件摘要和文件 mtime 不变。

**Checkpoint：** 目标文档 chunks 可稳定、只读加载。

**中文 commit：** `feat(eval): 实现评测文档只读加载`

### Task 4：生成并发布独立问题集

**阶段输入检查：**

- 已确认：目标文档 chunks 和问题分类；
- 缺失：无用户侧关键缺失；正式执行前验证问题生成环境变量；
- 默认：生成 seed 固定，每份文档三类问题各 1 条，不可回答问题不得伪造 `expected_article`。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和现有 OpenAI SDK/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/question_generator.py`
- 新建：`scripts/generate_ws_rag_dataset.py`
- 新建：`tests/eval_ws_rag/test_question_generator.py`
- 新建：`tests/eval_ws_rag/test_generate_dataset_cli.py`

**Step 0：实现前核验目标 provider 官方契约。**

按仓库联网规则只读取目标 provider 与 OpenAI Python SDK 官方文档，确认 `deepseek-v4-pro-260425` 的精确模型 ID、结构化输出、温度、超时和重试语义。若模型不存在或不支持严格结构化输出，停止 Task 4，报告差异并等待用户决定；不得静默换模型或降级为自由文本 JSON。

**Step 1：先写失败测试。**

使用 fake client，覆盖三类问题各 1 条、环境变量调整各类数量、稳定 `question_id`、去重、可回答条文存在、不可回答条文不存在、schema 非法响应停止、串行调用、临时失败只额外重试 1 次、密钥不落盘。

**Step 2：确认预期失败。**

**命令执行意图：** 证明问题生成器和独立 CLI 尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_question_generator.py tests/eval_ws_rag/test_generate_dataset_cli.py -q
```

**预期输出：** FAIL，原因是目标模块或 CLI 不存在。

**Step 3：最小实现。**

- `QuestionGeneratorClient` 使用可注入 `complete(messages)` 协议；
- 生成器只接收当前文档 chunks；
- 本地门禁验证条文存在性、负例不存在性、重复问题和切片覆盖；
- CLI 只生成 dataset，不运行检索、回答、Judge 或报告；
- `--document-id` 可重复传入；每份文件独立生成和校验问题，再共同写入不可变 `documents[]`；
- 正式命令必须显式提供至少一个 `--document-id`、`--dataset-id`、`--seed`，不得提供模型选择参数；
- 配置层从 `WS_RAG_QUESTION_GENERATOR_*` 读取模型连接，从三个 `WS_RAG_*_QUESTIONS_PER_DOCUMENT` 变量读取数量；
- 三类模型共用 `WS_RAG_MODEL_MAX_RETRIES=1`；问题生成器按文档和问题类型串行调用，不创建并发任务。

**Step 4：通过测试。**

**命令执行意图：** 验证问题生成和 CLI 边界。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_question_generator.py tests/eval_ws_rag/test_generate_dataset_cli.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

**命令执行意图：** 使用真实 W-S chunks 和 fake client 生成可复算 dataset。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_generate_dataset_cli.py -q -k real_chunks
```

**预期输出：** PASS；dataset 同时覆盖三类问题，fingerprint 重载一致，未执行 RAG。

**Checkpoint：** 问题集生成与评测执行在进程、CLI 和落盘产物上均分离。

**中文 commit：** `feat(eval): 实现独立问题集生成流程`

## 4. 分卷一完成门禁

**命令执行意图：** 执行分卷一全部测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_report_models.py tests/eval_ws_rag/test_dataset_store.py tests/eval_ws_rag/test_document_loader.py tests/eval_ws_rag/test_question_generator.py tests/eval_ws_rag/test_generate_dataset_cli.py -q
```

**预期输出：** 全部 PASS；无新增 skip/xfail。

进入分卷二前必须能给出一个已落盘 dataset 的 `dataset_id` 和 `dataset_fingerprint`。
