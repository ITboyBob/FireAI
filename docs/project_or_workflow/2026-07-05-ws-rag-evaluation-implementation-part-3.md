# Word/W 单文件 RAG 问答评测实施计划：分卷三

> 本分卷负责编排、未校准限制声明、首个基线登记、W-S1/W-S2 真实验收和文档收口。

## 1. 分卷入口检查

### 已确认

- 已有不可变 dataset、真实 RAG Runner、Judge、规则校验、聚合和原子发布；
- 正式方向性比较只能发生在 schema 主版本、`dataset_id`、`dataset_fingerprint`、`protocol_fingerprint` 及文档/问题 ID 全部相同的 run 之间；
- Dashboard 由独立实施计划消费共享报告模型。

### 缺失输入

- 分卷一、二完成后生成的正式 dataset；
- 通过真实验收后拟登记为 baseline 的首个 Run。

### 默认值

- run ID 采用本地时间戳加短随机后缀；
- 正式报告根目录 `reports/ws_rag_eval/`；
- baseline registry 为 `data/eval/ws_rag_baselines.json`，仅保存名称与不可变 run 引用；
- 目标文档为 `doc_d97773f1500c` 和 `doc_0e84d13a099b`，每份三类问题各 1 条；
- 三类模型串行调用，失败后最多额外重试 1 次；
- 无需新增依赖，全部命令使用 conda 环境 `fire`。

## 2. Phase 5：主编排、限制声明与基线

### Task 10：实现评测主 CLI 与错误收口

**阶段输入检查：**

- 已确认：输入必须是已持久化 dataset；
- 缺失：无用户侧关键缺失；启动时验证环境变量；
- 默认：CLI 不隐式生成问题，不接受裸 `document_id` 代替 dataset，也不接受模型选择参数。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和现有依赖，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/orchestrator.py`
- 新建：`scripts/evaluate_ws_rag.py`
- 新建：`tests/eval_ws_rag/test_orchestrator.py`
- 新建：`tests/eval_ws_rag/test_evaluate_cli.py`

**Step 1：先写失败测试。**

覆盖：

- 必填 `--dataset`、`--run-id`；
- 答案生成只读取 `CHAT_*`，问题生成和 Judge 只读取各自 `WS_RAG_*` 环境变量；
- 读取 dataset 后重新核验 fingerprint；
- preflight 检查 chunks、三个索引文件、模型精确版本、生成/Judge prompt 版本和输出冲突；
- 从 dataset 来源摘要及正式索引身份计算稳定 `corpus_fingerprint`，不得以目录 mtime 代替；
- 每题依次执行 Runner、Judge、规则并聚合；
- 可恢复问题错误进入 `errors.json` 并继续；
- Judge 最终失败、索引缺失、融合异常、schema 失败立即停止；
- 致命失败返回 `1`，正式 run 不存在，脱敏 debug 写入 `var/`；
- 成功返回 `0`，正式 run 同时包含两个 JSON；
- 输出日志明确打印 run ID、dataset 双标识、模型和最终路径。

**Step 2：确认预期失败。**

**命令执行意图：** 证明主编排和 CLI 尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_orchestrator.py tests/eval_ws_rag/test_evaluate_cli.py -q
```

**预期输出：** FAIL，原因是目标模块或 CLI 不存在。

**Step 3：最小实现。**

编排顺序固定为：

1. 读取配置和 dataset；
2. 完成只读 preflight；
3. 为每题执行真实 RAG；
4. 执行 Judge 和规则校验；
5. 聚合 report/errors；
6. 共享 schema 自校验；
7. run 目录级原子发布。

CLI 不提供 `--output reports/ws_rag_eval.json` 单文件旧语法，避免破坏 Dashboard 目录契约。

**Step 4：通过测试。**

**命令执行意图：** 验证成功、可恢复错误和致命错误三条编排路径。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_orchestrator.py tests/eval_ws_rag/test_evaluate_cli.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实上游产物验证。**

用真实 dataset/chunks/index，答案和 Judge 使用 fake client；验证除了模型外的完整链路。

**命令执行意图：** 执行真实索引离线集成验证。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_orchestrator.py -q -k real_index
```

**预期输出：** PASS，无 skip；临时目录中成对发布报告。

**Checkpoint：** 成功和失败均无半成品正式 run，CLI 不生成临时问题集。

**中文 commit：** `feat(eval): 贯通评测主编排与CLI`

### Task 11：固定未校准限制声明与配置审计

**阶段输入检查：**

- 已确认：本轮不执行人工校准，默认阈值只用于工程回归；
- 缺失：无；
- 默认：所有正式报告记录 `judge_calibrated=false`。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/runtime_config.py`
- 新建：`tests/eval_ws_rag/test_runtime_config.py`
- 修改：`scripts/eval_ws_rag/report_models.py`
- 修改：`tests/eval_ws_rag/fixtures/valid_report.json`
- 修改：`.env.example`

**Step 1：先写失败测试。**

覆盖：

- 答案生成模型只读取现有 `CHAT_*`；
- 问题生成与 Judge 分别读取独立 Key、URL、模型环境变量；
- 首轮精确模型 ID 与用户确认值一致；
- 三类问题数量环境变量默认均为 `1`；
- 三类模型调用并发固定为 `1`，`WS_RAG_MODEL_MAX_RETRIES=1`；
- Judge 温度固定为 `0`；
- 配置日志和报告不包含 API Key；
- 报告缺少 `judge_calibrated=false` 时 schema 校验失败。

**Step 2：确认预期失败。**

**命令执行意图：** 证明统一运行配置和限制字段尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_runtime_config.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

实现只读运行配置模型，集中校验三类模型身份、连接配置、超时、重试、串行策略和问题数量。报告协议增加 `judge_calibrated`，首轮只能写 `false`。文档与 CLI 帮助必须明确：

- Judge 分数未经人工或专家校准；
- 六条问题只用于端到端工程验收；
- 默认阈值不能解释为法律专业准确率；
- 未来若启用人工校准，应新增独立计划和版本化校准记录，不能修改本轮历史 Run。

**Step 4：通过测试。**

**命令执行意图：** 验证环境变量边界、串行重试和未校准声明。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_runtime_config.py -q
```

**预期输出：** 全部 PASS。

**Step 5：配置只读验证。**

**命令执行意图：** 查看脱敏后的运行配置摘要。

```bash
conda run -n fire python scripts/evaluate_ws_rag.py --show-config
```

**预期输出：** 显示三类模型 ID、问题数量、串行策略、额外重试次数和 `judge_calibrated=false`；不显示 Key、不调用模型、不写报告。

**Checkpoint：** 模型配置可审计，未校准边界无法被报告或页面隐藏。

**中文 commit：** `feat(eval): 固定评测模型配置与未校准声明`

### Task 12：建立不可变基线登记与同 dataset 比较

**阶段输入检查：**

- 已确认：比较不能混用不同问题集；
- 缺失：经真实验收的首个 baseline run；
- 默认：registry 只保存引用，不复制或覆盖 run 内容。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/baseline.py`
- 新建：`scripts/compare_ws_rag_runs.py`
- 新建：`tests/eval_ws_rag/test_baseline.py`
- 生成：`data/eval/ws_rag_baselines.json`

**Step 1：先写失败测试。**

覆盖：

- baseline 名称只能指向已存在且 schema 有效的不可变 run；
- schema 主版本、dataset ID/fingerprint、protocol fingerprint 或文档/问题 ID 不同进入“非同口径”，只允许并排查看，不计算方向变化；
- 六项指标、总体通过率、失败数和三类红线差异正确；
- 基于相同 question ID 计算 current 的 win/tie/loss 和 Win Rate；
- `system` 差异明确列出，作为被测变量展示，不静默忽略；
- 同一 baseline 名称默认禁止覆盖，显式替换需记录前后 run；
- baseline registry 损坏时不修改。
- 首轮只有 baseline 时返回“等待 current Run”，不得伪造方向性变化。

**Step 2：确认预期失败。**

**命令执行意图：** 证明基线和比较模块尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_baseline.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

实现 `register_baseline()`、`load_baseline()`、`compare_runs()`；比较输出是派生结果，不生成第二份事实报告。Dashboard 两轮对比仍直接读取两个 run。

**Step 4：通过测试。**

**命令执行意图：** 验证同 dataset 门禁与差异计算。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_baseline.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实报告验证。**

**命令执行意图：** 查看比较 CLI 参数和保护条件。

```bash
conda run -n fire python scripts/compare_ws_rag_runs.py --help
```

**预期输出：** 显示 baseline/current run 参数，并说明 dataset 不一致时退出码为 `2`。

只有真实 baseline run 可用后才登记；mock run 不得成为正式 baseline。本轮登记首个 baseline 后即完成该真实步骤，不要求为了凑比较而重复同一配置；比较算法和同口径门禁仍由 fixture 测试覆盖。

**Checkpoint：** 任意可比较结论都能追溯到同一不可变问题集。

**中文 commit：** `feat(eval): 建立评测基线与同集比较`

## 3. Phase 6：W-S1/W-S2 真实验收与文档收口

### Task 13：完成真实模型验收、回归和文档同步

**阶段输入检查：**

- 已确认：W-S1/W-S2 正式 chunks 和索引存在；
- 缺失：无用户侧关键缺失；运行前验证环境变量和 provider 可用；
- 默认：固定使用 `doc_d97773f1500c`、`doc_0e84d13a099b`，每份三类问题各 1 条；首个 Run 登记 baseline，不生成 current Run。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和现有依赖，无需新增依赖；Dashboard 按独立计划处理，不在本 Task 安装 Streamlit；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/verify_ws_rag_evaluation_run.py`
- 新建：`tests/eval_ws_rag/test_real_run_verifier.py`
- 修改：`docs/architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md`
- 修改：`docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md`
- 修改：`docs/system_meta/文档索引.md`
- 修改：`docs/system_meta/文档读取规则.md`
- 按运行生成：`reports/ws_rag_eval/<run_id>/report.json`
- 按运行生成：`reports/ws_rag_eval/<run_id>/errors.json`

**Step 1：先写失败的真实产物验证器测试。**

固定：

- 验证器只读指定 dataset、run 和正式 chunks/index，不调用外部模型；
- 真实 dataset 可加载且来源摘要与正式 chunks 一致；
- 报告以嵌套 `dataset`、`protocol`、`system` 记录 dataset/protocol 双指纹、模型精确版本、Git commit/dirty 状态、语料指纹、阈值、prompt 版本、证据顺序策略和 `judge_calibrated=false`；
- 两个报告文件同目录成对存在且共享 schema 可重载；
- report/errors、文件、问题、证据和引文的跨字段一致性通过；
- 非法或半成品 run 返回非零退出码；
- 单元测试不依赖 API 凭据、网络或已经存在的真实 run。

**Step 2：确认预期失败。**

**命令执行意图：** 证明真实产物验证器尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_real_run_verifier.py -q
```

**预期输出：** FAIL，原因是验证器模块或 CLI 不存在。

**Step 3：实现并通过确定性验证器测试。**

实现 `verify_real_run(dataset_path, run_path, data_dir)` 和只读 CLI。它只验证已经生成的产物，不触发问题生成、回答生成或 Judge。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_real_run_verifier.py -q
```

**预期输出：** 全部 PASS，无 skip/xfail，且不访问网络。

**Step 4：执行显式真实模型运行。**

先生成或确认同时包含 W-S1、W-S2 文档的正式 dataset，再使用主 CLI 执行。每条终端命令只处理一个明确动作；凭据只从环境读取，不写入命令、报告或 Git。

**命令执行意图：** 查看 dataset 生成参数，确认不会隐式运行评测。

```bash
conda run -n fire python scripts/generate_ws_rag_dataset.py --help
```

**预期输出：** 显示 document、dataset ID 和 seed 参数；模型从环境读取，帮助中不存在模型选择参数。

**命令执行意图：** 查看评测运行参数，确认输入要求为 dataset。

```bash
conda run -n fire python scripts/evaluate_ws_rag.py --help
```

**预期输出：** 显示 dataset、run ID 和报告根目录参数；模型从环境读取，帮助中不存在模型选择参数。

正式运行命令中的实际 dataset ID 和 run ID 由阶段输入检查结果填写；模型身份来自已确认环境变量。

真实验收必须实际完成：独立 dataset 生成、真实 Retriever、真实答案生成模型、真实且独立的 Judge、run 目录级原子发布。凭据缺失、网络失败或模型调用失败都表示本阶段未完成，不得改成 pytest skip，也不得用 fake client 替代。

**Step 5：核验真实 Run。**

**命令执行意图：** 对已发布的 W-S1/W-S2 联合真实 Run 执行只读核验。

```bash
conda run -n fire python scripts/verify_ws_rag_evaluation_run.py --dataset <dataset.json> --run <run目录> --data-dir data
```

**预期输出：** 退出码 `0`，打印 dataset/run 双标识、文档数、问题数和一致性通过结论。

**Step 6：通过自动化回归。**

**命令执行意图：** 执行评测系统全部测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag -q
```

**预期输出：** 全部 PASS，无新增 warning、skip 或 xfail；测试不调用外部模型。

**命令执行意图：** 执行仓库完整回归。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS。

**Step 7：真实报告人工核对与状态更新。**

本轮不执行人工校准。实现者只做产物一致性核对：

- 目标条文是否在原始 top-k；
- 回答与引文是否可回溯；
- 负例是否正确拒答；
- 报告聚合是否与问题明细一致；
- 正式 run 不含密钥、完整 prompt 和半成品。

仅在代码、测试、真实模型评测、未校准限制声明和首个 baseline 登记全部完成后，将主评测能力更新为 `implemented`；否则如实保持 `in_progress` 或 `planned`。`implemented` 只表示工程链路完成，不代表 Judge 获得法律专家校准。

文档中 Dashboard 执行入口只链接：

[W-S RAG 评测 Dashboard 实施计划](./2026-07-05-ws-rag-evaluation-dashboard-implementation.md)

不得复制其 Streamlit Phase。

**Checkpoint：** W-S1/W-S2 真实证据、未校准限制、首个 baseline 和文档状态一致。

**中文 commit：** `test(eval): 完成Word评测真实验收与文档收口`

### Task 13 真实运行结果记录

本轮真实验收已完成，结果如下：

- **dataset ID：** `ws_rag_baseline_001`
- **run ID：** `ws_rag_baseline_001_run_001`
- **baseline 名称：** `ws_rag_baseline_001`
- **来源文档：**
  - W-S1 `doc_d97773f1500c`《消防监督检查规定》
  - W-S2 `doc_0e84d13a099b`《河北省消防设施管理规定》
- **问题构成：** 每份文档高频、边界、多样性各 1 题，共 6 题
- **产物位置：** `reports/ws_rag_eval/ws_rag_baseline_001_run_001/report.json` 与 `errors.json` 成对存在

**实际模型分工与切换原因：**

- 答案生成：`doubao-1-5-lite-32k-250115`
- 问题生成：`doubao-seed-2-1-pro-260628`（原配置 `deepseek-v4-pro-260425` 在火山方舟上不支持 `json_schema`）
- Judge：`deepseek-v4-pro-260425`（原配置 `doubao-seed-2-1-pro-260628` 在火山方舟上结构化/数组输出长时间无响应）
- 所有报告均声明 `judge_calibrated=false`

**核验命令及结果：**

```bash
conda run -n fire python scripts/verify_ws_rag_evaluation_run.py \
  --dataset data/eval/ws_rag_datasets/ws_rag_baseline_001/dataset.json \
  --run reports/ws_rag_eval/ws_rag_baseline_001_run_001 \
  --data-dir data
```

退出码 `0`，产物一致性通过。

**回归测试结果：**

- `tests/eval_ws_rag`：197 passed
- 仓库完整回归：672 passed

**关键 commit：**

- `f74e00f` text JSON 回退修复
- `98a14c8` embedder 与引文绑定修复
- `fecb702` 首个真实 dataset/Run/baseline

## 4. 分卷三完成门禁

**命令执行意图：** 检查所有评测计划和设计文档引用。

```bash
rg -n "ws-rag-evaluation-(design|implementation|dashboard)" docs
```

**预期输出：** 主设计、主计划、Dashboard 设计和 Dashboard 计划互相指向正确职责，不存在复制的 Dashboard 实施步骤。

**命令执行意图：** 检查计划文件格式。

```bash
git diff --check
```

**预期输出：** 无输出。

本分卷完成不自动代表 Dashboard 已实现；Dashboard 首轮状态由其独立计划和单 mock Run 页面证据决定，能力仍保持 `planned`。
