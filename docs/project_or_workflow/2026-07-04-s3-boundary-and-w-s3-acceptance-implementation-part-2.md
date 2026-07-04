# S3 边界能力与 W-S3 组合验收实施计划（分卷二）

> **执行状态：已完成。** Task 6—8 已分别由提交 `62d4e0b`、`c8b96c2`、`f184086` 完成并验证。下文保留正式写入门禁和命令作为审计记录。
>
> 本卷执行 Task 6—8：完成真实 CLI 预演、临时 Append-Only 与回滚验收，再正式导入唯一 W-S3 文件。只有全部前置门禁通过，Task 8 才能写正式 `data/`。

**目标：** 使用唯一 CLI 显式选择 `W + S3`，让真实文件经过 v3 质量资格、临时提交与完整回归后，正式进入语料、关键词索引、FAISS 索引和 manifest。

**架构：** CLI 只传递双轴筛选条件，不包含 S3 业务规则。正式提交继续复用单文件 staging、两次 preflight、索引副本、失败回滚和 manifest 最后写入；批次只选择 1 项、调度并汇总。

**技术栈：** Python 3.14、pytest、现有 CLI、Append-Only 服务、关键词检索和 `faiss-cpu==1.14.3`；无需新增依赖。

---

## 1. 权威输入与本卷边界

- [总计划](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation.md)
- [分卷一](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation-part-1.md)
- [S3 专项设计](../architecture_or_strategy/2026-07-04-s3-trailing-exclusion-boundary-design.md)
- [Append-Only 实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)

Task 6 只允许生成 dry-run 报告；Task 7 只能写临时目录；Task 8 是本计划唯一允许写正式 `data/` 的 Task，且只允许提交唯一清单内 W-S3 文件。

## Phase 2：真实验收、正式提交与收口（已完成）

### 执行前已确认

- 分卷一 Task 1—5 必须全部通过；
- W-S3 应形成 quality v3 overall PASS；
- 唯一 CLI 已支持 `--extraction-class W --content-class S3` 的通用参数；
- 现有 Append-Only 事务已由 W-S1/W-S2 验证，不应重写；
- 正式导入不可通过简单覆盖修复，必须先完成 dry-run 和临时提交；
- 正式提交前必须知道干净 chunk 数，但不得沿用污染的 37。

### 执行前待补齐（现已完成）

- Task 6 已通过 confirmed 29 条正文、生成结果和人工核对把干净 chunk 数冻结为 34；
- Task 8 已生成并核验源摘要、正式 20/876/876 索引数量、14 条 manifest 记录和正式批次标识；
- 若正式数据在 Task 6—8 期间被其他进程修改，必须重新建立基线。

### 默认值

- 不新增依赖；
- CLI 不传双轴参数时继续默认 `W + S1`，保持兼容；
- W-S3 必须显式传 `--extraction-class W --content-class S3`；
- 任何数量、摘要、边界或检索不一致都先停止调查，不通过修改断言适配异常；
- 正式命令只执行一次；若失败，不重复整批命令；
- 正式提交失败时路线图保持 `in_progress/planned`，不得标成 implemented。

### 依赖与包管理工具

- 后端：conda 环境 `fire`，本 Phase 无需新增依赖；
- 前端：不涉及；
- 索引：沿用现有关键词索引和 FAISS 1.14.3，不安装、不全量重建；
- Git：每个 Task 通过后按总计划执行中文 commit，不 push；
- Linear：仅 Task 8 全部验收通过后更新既有里程碑，不创建新 issue。

### Task 6：执行真实来源核验、dry-run 并冻结干净 chunk 数

**阶段输入检查：**

- 已确认：分卷一全部通过；W-S3 v3 质量报告为 PASS；
- 缺失：真实 CLI 报告和干净 chunk 数；
- 依赖：无需新增依赖。

**文件：**

- 新增：`tests/integration/pipeline/test_ws3_batch.py`
- 新增：`tests/integration/pipeline/test_ws3_batch_report_real.py`
- 必要时修改：`scripts/import_new_corpus.py`
- 修改：`README.md`
- 生成但不提交为正式语料：`data/manifests/legal_ingestion_batches/<run_id>/`

只有测试证明现有通用筛选存在缺口时，才允许最小修改 CLI。禁止新增 `--ws3` 或第二个脚本。

**步骤 1：先写失败批次测试。**

测试固定：

- 显式 `W + S3` 恰好选择 1 项；
- 旧命令不传参数仍选择 W-S1；
- `PT + S3` 或 `PS + S3` 只按 manifest 选择，但未实现提取策略时稳定返回 unsupported；
- 非法枚举由 argparse 拒绝；
- 单文件模式传批次筛选参数时报错并零写入；
- 空选择返回清晰结果，不扫描目录；
- 筛选只比较 manifest 双轴字段，不根据文件名猜测。

**命令执行意图：** 验证当前通用 CLI 能否安全选择唯一 W-S3。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws3_batch.py tests/integration/pipeline/test_ws1_batch.py tests/integration/pipeline/test_ws2_batch.py -q
```

**预期输出：** 新 W-S3 测试首次因文件尚未实现而 FAIL；若现有 CLI 已满足业务行为，补齐测试后应直接 PASS，不为制造改动而修改生产代码。

**步骤 2：执行来源只读核验。**

**命令执行意图：** 核对清单、真实路径、双轴分类和源摘要，不处理正文、不提交。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S3 --verify-source-only
```

**预期输出：** `selected=1`、`failed=0`；来源摘要与读取前一致。selected 不是 1 时停止。

**步骤 3：执行真实 dry-run。**

**命令执行意图：** 走完整 W 提取、S3 边界、结构解析、切块和 v3 质量门禁，但不调用正式 commit。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S3 --dry-run
```

**预期输出：** `selected=1`、`committed=0`、`auto_passed=1`、`review_required=0`、`failed=0`、`unsupported=0`，并输出唯一报告路径。

**步骤 4：自动验证报告和干净产物。**

`test_ws3_batch_report_real.py` 必须断言：

- source item 有独立 source_sha256、document_id、质量报告和 disposition；
- ruleset 为 v3，四项 S3 gate 及通用 gate 全部 PASS；
- dry_run=true、commit result 为空；
- structured 为 29 条，第二十九条无尾部污染；
- chunks 只覆盖 29 条正文，数量与当次实际生成一致；
- 报告不复制排除正文；
- 正式语料、索引和 manifest 摘要前后不变。

由人工对照真实源文件确认每个 chunk 都来自正文后，把当次干净 chunk 数固定为后续 W-S3 测试常量。该常量属于验收结果，不得回写成第二份来源清单。

**命令执行意图：** 验证报告、零正式写入和干净 chunk 数。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws3_batch.py tests/integration/pipeline/test_ws3_batch_report_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；正式 `data/` 摘要不变。

**步骤 5：更新 README 计划用法。**

在 README 增加显式 W-S3 dry-run 示例，并明确当前步骤只证明质量资格、不代表正式导入。每条命令都要附执行意图和预期输出。

**Checkpoint：** 已取得真实提交资格并冻结干净 chunk 数，但尚未验证事务和检索。验证完成后按总计划提交：`完成W-S3真实预演验收`。

### Task 7：在临时目录验证 Append-Only、回滚和检索

**阶段输入检查：**

- 已确认：Task 6 的真实 dry-run 和干净 chunk 数已固定；
- 缺失：临时提交、失败回滚和检索闭环；
- 依赖：无需新增依赖。

**文件：**

- 新增：`tests/integration/pipeline/test_ws3_qualified_incremental_import.py`
- 修改：`tests/unit/services/test_retriever.py`
- 按真实失败最小修改：现有 Append-Only 服务及其测试

不得预先重写事务。只有新增测试证明既有通用提交存在 S3 兼容缺口时，才允许最小修复。

**步骤 1：先写临时提交测试。**

在 `tmp_path` 复制最小正式基线和索引，再提交真实 W-S3，断言：

- committed=1；
- normalized、structured、chunks 和 manifest 各增加 1 个目标记录；
- keyword chunk 与 FAISS vector 增量等于 Task 6 冻结的干净 chunk 数；
- FAISS 维度、模型标识和旧向量不变；
- structured 恰好 29 条；
- manifest 保存 source_sha256、artifact digests、quality digest 和 run_id；
- 标题和正文独有条文可以通过关键词、向量入口命中；
- 只存在于尾部模板、正文中不存在的代表性文本不能命中该文档。

**命令执行意图：** 证明 W-S3 尚未完成临时提交与检索闭环。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws3_qualified_incremental_import.py -q
```

**预期输出：** 首次因测试尚未实现或暴露真实兼容缺口而 FAIL。

**步骤 2：验证来源或 staged 摘要失败。**

注入来源摘要变化或 staged artifact digest 不一致，断言：

- 结果 failed；
- normalized、structured、chunks、关键词索引、FAISS 和 manifest 均保持提交前摘要；
- 不产生残留 staging；
- 失败不能降级为 review 或 unsupported。

**步骤 3：验证索引和 manifest 发布失败回滚。**

分别注入：

- 关键词或 FAISS 索引替换失败；
- manifest 最后写入失败。

每种情况下均断言正式语料、两类索引和 manifest 回到提交前状态；任何回滚不完整都必须让测试失败并停止实施。

**步骤 4：运行相关回归。**

**命令执行意图：** 验证 W-S3 临时提交、失败路径和 W-S1/W-S2 既有提交均稳定。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws3_qualified_incremental_import.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py tests/integration/pipeline/test_ws2_qualified_incremental_import.py tests/unit/services/test_retriever.py -q
```

**预期输出：** 全部 PASS；所有测试只写临时目录。

**步骤 5：在正式写入前运行完整回归。**

**命令执行意图：** 发现计划范围外的兼容性破坏。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；不得新增 warning、skip 或 xfail。任何失败都阻止 Task 8。

**Checkpoint：** S3 已完成临时事务和检索验收，但正式数据仍未改变。验证完成后按总计划提交：`验证W-S3临时提交与回滚`。

### Task 8：正式导入唯一 W-S3 文件并同步状态

**阶段输入检查：**

- 已确认：Task 1—7 全部完成并提交；完整回归通过；
- 缺失：正式写入前易变基线、正式 run_id 和最终总数；
- 依赖：无需新增依赖；Linear 连接仅用于成功后的状态同步。

**文件：**

- 新增：正式 `data/normalized/`、`data/structured/`、`data/chunks/` 对应目标产物
- 修改：正式关键词索引、FAISS 索引和增量 manifest
- 新增：`data/manifests/legal_ingestion_batches/<run_id>/` 正式批次报告
- 新增：`tests/integration/pipeline/test_ws3_formal_index_state.py`
- 修改：`docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md`
- 修改：`README.md`
- 必要时修改：`docs/system_meta/文档索引.md`、`docs/system_meta/文档读取规则.md`
- 外部同步：Linear“消防AI”项目的“W-S3 尾部排除内容”里程碑

**步骤 1：建立正式写入前基线。**

记录：

- `git status --short`，区分用户已有改动；
- 真实源 SHA-256；
- 当前 document、keyword chunk、FAISS vector 和 manifest 数量；
- FAISS 维度与模型标识；
- W-S1 8 份、W-S2 2 份可检索证据；
- Task 6 dry-run 报告路径、摘要和干净 chunk 数；
- 正式数据目录与索引内部数量是否一致。

工作区有无法避开的无关改动、源摘要变化、正式索引不一致或 Linear 目标里程碑无法唯一解析时立即停止。

**步骤 2：重新执行来源核验和 dry-run。**

**命令执行意图：** 在正式写入前证明来源和质量结论仍与 Task 6 一致。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S3 --dry-run
```

**预期输出：** `selected=1`、`auto_passed=1`、`review_required=0`、`failed=0`、`unsupported=0`；source SHA-256 和 chunk 数与 Task 6 一致。

**步骤 3：只执行一次正式命令。**

**命令执行意图：** 通过唯一 CLI 对清单中的 1 份 W-S3 执行 v3 资格和 Append-Only 正式提交。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S3
```

**预期输出：** 新 run_id；`selected=1`、`committed=1`、`review_required=0`、`failed=0`、`unsupported=0`。失败时不得重复整批命令。

**步骤 4：验证正式状态。**

`test_ws3_formal_index_state.py` 读取正式产物并断言：

- 目标 document_id 在 normalized、structured、chunks、关键词索引、FAISS 映射和 manifest 中各出现一次；
- 正式增量相对步骤 1 为 document +1，chunk/vector +干净 chunk 数，manifest +1；
- structured 为 29 条，质量报告为 v3 PASS；
- 第二十九条和所有 chunks 无尾部污染；
- 标题和正文检索命中目标文档；
- 尾部专属代表性文本不命中目标文档；
- W-S1/W-S2 共 10 份已验收文件仍存在且可检索；
- 重复源摘要没有第二条 manifest。

**命令执行意图：** 验证控制台 `committed=1` 与所有正式存储事实一致。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws3_formal_index_state.py tests/unit/services/test_retriever.py -q
```

**预期输出：** 全部 PASS；正式语料、两类索引、manifest 和报告一致。

**步骤 5：同步仓库和 Linear 状态。**

仅在步骤 3—4 全部成功后：

- 将 S3 与 W-S3 更新为 `implemented`；
- 将 14 文件验收进度更新为 11/14，剩余 3 份 PDF；
- 路线图记录真实 run_id、最终数量、测试结果和 commit 证据；
- README 将 W-S3 命令更新为已支持用法；
- 新增或移动文档时同步索引、读取规则和所有入口；
- Linear 里程碑描述已写入 29 条正文、v3 门禁、正式索引和回归证据并标记完成；当前无关联 issue，计算型 `progress` 仍为 0，不作为能力状态依据；
- 不创建后续 issue，不开始 PT/PS/OCR。

若正式提交未成功，仓库和 Linear 只能如实记录 `in_progress` 或失败状态，禁止写成 implemented。

**步骤 6：最终完整回归和提交。**

**命令执行意图：** 在正式产物与状态同步后重新执行仓库完整回归。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；正式 W-S3 状态测试已被收集，不得新增 warning、skip 或 xfail。

确认 `git diff --cached` 只包含 Task 8 的正式产物、测试、文档和状态同步后，按总计划提交：`完成W-S3正式导入与状态同步`。不得 push。

## 2. 分卷完成检查

分卷完成必须同时具备：

- 显式 W-S3 命令只选择 1 项，旧 W-S1/W-S2 命令兼容；
- verify-source-only 和 dry-run 结果正确；
- 干净 chunk 数基于 confirmed 29 条正文冻结；
- 临时提交、摘要失败、索引失败、manifest 失败和回滚均通过；
- 正式批次为 committed=1；
- 正式语料、关键词索引、FAISS、manifest、质量报告和检索一致；
- W-S1/W-S2 真实回归及仓库完整测试通过；
- 路线图、README、文档系统和 Linear 只依据真实结果更新。

只完成策略、CLI 选择或 dry-run，不得执行 Task 8 commit，也不得把 S3/W-S3 标记为 implemented。
