# Word/W 单文件 RAG 问答评测实施计划：分卷三

> 本分卷负责编排、人工校准、基线比较、W-S1/W-S2 真实验收和文档收口。

## 1. 分卷入口检查

### 已确认

- 已有不可变 dataset、真实 RAG Runner、Judge、规则校验、聚合和原子发布；
- 正式方向性比较只能发生在 schema 主版本、`dataset_id`、`dataset_fingerprint`、`protocol_fingerprint` 及文档/问题 ID 全部相同的 run 之间；
- Dashboard 由独立实施计划消费共享报告模型。

### 缺失输入

- 正式生成/Judge 模型及凭据；
- 用户确认的校准样本与人工评审者；
- 拟登记 baseline 的真实 run；
- W-S1、W-S2 各一份目标真实文件。

### 默认值

- run ID 采用本地时间戳加短随机后缀；
- 正式报告根目录 `reports/ws_rag_eval/`；
- baseline registry 为 `data/eval/ws_rag_baselines.json`，仅保存名称与不可变 run 引用；
- 无需新增依赖，全部命令使用 conda 环境 `fire`。

## 2. Phase 5：主编排、校准与基线

### Task 10：实现评测主 CLI 与错误收口

**阶段输入检查：**

- 已确认：输入必须是已持久化 dataset；
- 缺失：正式执行模型配置；
- 默认：CLI 不隐式生成问题，不接受裸 `document_id` 代替 dataset。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和现有依赖，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/orchestrator.py`
- 新建：`scripts/evaluate_ws_rag.py`
- 新建：`tests/eval_ws_rag/test_orchestrator.py`
- 新建：`tests/eval_ws_rag/test_evaluate_cli.py`

**Step 1：先写失败测试。**

覆盖：

- 必填 `--dataset`、`--generation-model`、`--judge-model`、`--run-id`；
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

### Task 11：建立人工校准与阈值审批记录

**阶段输入检查：**

- 已确认：换 Judge 模型或 prompt 后必须重新校准；
- 缺失：人工评审者、正式模型和 50～100 条样本；
- 默认：20 条仅作试运行，不能代替正式校准。

**依赖与包管理：** 后端使用 conda 环境 `fire` 和标准库/Pydantic，无需新增依赖；前端和其他运行环境不涉及。

**文件：**

- 新建：`scripts/eval_ws_rag/calibration.py`
- 新建：`scripts/calibrate_ws_rag_judge.py`
- 新建：`tests/eval_ws_rag/test_calibration.py`
- 生成：`data/eval/ws_rag_calibrations/<calibration_id>.json`

**Step 1：先写失败测试。**

覆盖稳定抽样、20 条 pilot 标记、50～100 条正式门禁、人工/Judge 一致率、红线误判计数、争议项保留、模型/prompt/阈值绑定、低于样本门槛禁止批准。

**Step 2：确认预期失败。**

**命令执行意图：** 证明校准模块尚不存在。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_calibration.py -q
```

**预期输出：** FAIL，原因是目标模块不存在。

**Step 3：最小实现。**

校准记录必须包含：

- 来源 run 和 dataset 双标识；
- Judge 模型、prompt 版本、seed 和重复次数；
- 样本问题 ID、人工标签、Judge 标签；
- 一致率、各红线的误报/漏报、争议说明；
- 建议阈值、批准人、批准时间和状态。

CLI 只汇总人工填写的标注文件，不用 Judge 结果覆盖人工裁决。

**Step 4：通过测试。**

**命令执行意图：** 验证校准样本门禁和统计。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_calibration.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实报告验证。**

**命令执行意图：** 从真实 run 稳定抽样并生成待标注模板。

```bash
conda run -n fire python scripts/calibrate_ws_rag_judge.py --help
```

**预期输出：** 显示抽样、导入人工标注和生成校准记录参数；不调用模型、不修改报告。

人工完成 50～100 条后再次执行汇总；在此之前本 Task 保持未完成。

**Checkpoint：** 阈值有人工证据，模型或 prompt 变化会使旧校准失效。

**中文 commit：** `feat(eval): 建立Judge人工校准流程`

### Task 12：建立不可变基线登记与同 dataset 比较

**阶段输入检查：**

- 已确认：比较不能混用不同问题集；
- 缺失：经真实验收和校准的 baseline run；
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

只有真实 baseline run 可用后才登记；mock run 不得成为正式 baseline。

**Checkpoint：** 任意可比较结论都能追溯到同一不可变问题集。

**中文 commit：** `feat(eval): 建立评测基线与同集比较`

## 3. Phase 6：W-S1/W-S2 真实验收与文档收口

### Task 13：完成真实模型验收、回归和文档同步

**阶段输入检查：**

- 已确认：W-S1/W-S2 正式 chunks 和索引存在；
- 缺失：用户提供正式模型凭据、确认两份目标文档、完成校准审批；
- 默认：每类至少一份文件，使用同一正式 dataset 版本做 baseline/current 比较。

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
- 报告以嵌套 `dataset`、`protocol`、`system` 记录 dataset/protocol 双指纹、模型精确版本、Git commit/dirty 状态、语料指纹、阈值、prompt 版本和证据顺序策略；
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

**预期输出：** 显示 document、model、dataset ID 和 seed 参数。

**命令执行意图：** 查看评测运行参数，确认输入要求为 dataset。

```bash
conda run -n fire python scripts/evaluate_ws_rag.py --help
```

**预期输出：** 显示 dataset、生成模型、Judge 模型、run ID 和报告根目录参数。

正式运行命令中的实际 ID 和模型名由阶段输入检查结果填写，禁止在计划中伪造。

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

人工核对至少 10% 问题且不少于 10 条；正式校准仍按 Task 11 的 50～100 条门禁。核对：

- 目标条文是否在原始 top-k；
- 回答与引文是否可回溯；
- 负例是否正确拒答；
- 报告聚合是否与问题明细一致；
- 正式 run 不含密钥、完整 prompt 和半成品。

仅在代码、测试、真实模型评测、校准和基线全部完成后，将能力路线图更新为 `implemented`；否则如实保持 `in_progress` 或 `planned`。

文档中 Dashboard 执行入口只链接：

[W-S RAG 评测 Dashboard 实施计划](./2026-07-05-ws-rag-evaluation-dashboard-implementation.md)

不得复制其 Streamlit Phase。

**Checkpoint：** W-S1/W-S2 真实证据、人工校准、基线和文档状态一致。

**中文 commit：** `test(eval): 完成Word评测真实验收与文档收口`

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

本分卷完成不自动代表 Dashboard 已实现；Dashboard 状态由其独立计划和真实页面证据决定。
