# S2 边界能力与 W-S2 组合验收实施计划（分卷三）

> 本卷执行 Task 7—10：通用化批次筛选，完成真实 dry-run、临时提交和正式导入。只有全部前置门禁通过，Task 10 才能写正式 `data/`。

**目标：** 使用唯一 CLI 显式选择 `W + S2`，让两份真实文件经过 v2 质量资格、临时 Append-Only 验收和完整回归后正式进入语料、关键词索引、FAISS 索引与 manifest。

**架构：** CLI 只把用户选择的双轴条件传给统一编排器，不实现 W-S2 业务逻辑。正式提交继续按单文件执行 staging、两次 preflight、索引副本发布、回滚和 manifest 最后写入；批次只负责选择、逐文件调度和汇总。

**技术栈：** Python 3.14、argparse、pytest、现有 Append-Only 服务、关键词检索、`faiss-cpu==1.14.3`；无需新增依赖。

---

## 1. 权威输入与本卷边界

- [总计划](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation.md)
- [分卷二](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation-part-2.md)
- [Append-Only 实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)

Task 7—9 只能写 `tmp_path`。Task 10 是本计划唯一允许写正式 `data/` 的步骤，且只允许提交两份清单内 W-S2 文件。

## Phase 3：批次选择、真实提交与收口

### 已确认

- 分卷一和分卷二必须全部通过；
- 两份 W-S2 均应为 quality v2 overall PASS；
- 唯一 CLI 为 `scripts/import_new_corpus.py`；
- 当前批次清单选择逻辑硬编码 `W + S1`，不能直接安全选择 W-S2；
- 现有 Append-Only 事务和索引格式已经由 W-S1 验证，不应重写；
- 正式导入属于不可通过简单删除一行完全撤销的数据操作，必须先完成临时验证。

### 缺失

- Task 10 执行时的正式文档数、chunk 数、向量数、manifest 条数和源 SHA-256 尚未冻结；
- 正式导入的 batch_id 只能在运行时生成，计划不预设；
- 若正式数据在 Task 7—9 期间被其他进程修改，必须重新建立基线。

### 默认值

- 不新增依赖；
- `--batch-manifest` 未显式传双轴参数时继续默认 `W + S1`，兼容现有 W-S1 命令；
- W-S2 必须显式传 `--extraction-class W --content-class S2`；
- 传双轴参数但未传 `--batch-manifest` 时参数错误并零写入；
- 正式批次中单份失败不回滚另一份已成功文件，但里程碑不能标记完成；
- 任何预期数值不一致都先停下调查，不以修改断言适配异常。

### 依赖与包管理工具

- 后端：conda 环境 `fire`，无需新增依赖；
- 前端：不涉及；
- 索引：沿用现有关键词索引和 FAISS 1.14.3，不安装、不重建全部索引；
- Git：只在 Phase 完整通过后按总计划提交，不 push。

### Task 7：把批次清单筛选改为通用双轴参数

**文件：**

- 修改：`scripts/import_new_corpus.py`
- 修改：`tests/integration/pipeline/test_ws1_batch.py`
- 新增：`tests/integration/pipeline/test_ws2_batch.py`
- 修改：`README.md`

**步骤 1：先写失败 CLI 测试。**

新增参数：

- `--extraction-class`：choices 来自可执行提取枚举，批次默认 `W`；
- `--content-class`：choices 来自内容枚举，批次默认 `S1`。

测试固定：

- 旧 `--batch-manifest` 命令不传新参数时仍选 8 项 W-S1；
- 显式 `W + S2` 恰好选 2 项；
- `PT + S2` 只选择对应清单项，但因 PT 未实现稳定返回 unsupported，零写入；
- 非法枚举值由 argparse 拒绝；
- 单文件模式传双轴筛选参数时报参数组合错误；
- 空选择返回清晰错误或零项报告，不发现式扫描目录；
- 筛选只比较 manifest 的两个 expected 字段，不根据后缀或文件名猜测。

**命令执行意图：** 证明当前硬编码筛选无法选择 W-S2。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_batch.py tests/integration/pipeline/test_ws2_batch.py -q
```

**预期输出：** 新 W-S2 测试因参数不存在或仍选 W-S1 而 FAIL。

**步骤 2：最小修改。**

把 `_resolve_manifest_sources()` 改为显式接收 `extraction_class` 和 `content_class`；main 只解析并传参。不得新增 `--ws2`、第二个脚本或目录自动发现。

README 同时保留旧兼容命令，并新增：

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest /absolute/path/to/manifest.json --source-root /absolute/path/to/source-root --extraction-class W --content-class S2 --dry-run
```

这条命令的文字说明必须明确：它只选择清单中的 W-S2 条目；`--dry-run` 会完整提取和验质，但不提交正式数据。

**步骤 3：回归参数与退出码。**

**命令执行意图：** 验证新旧批次选择、互斥参数和零写入错误路径。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_batch.py tests/integration/pipeline/test_ws2_batch.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** 全部 PASS；旧 W-S1 调用兼容，W-S2 显式选择 2 项。

**Checkpoint：** CLI 能选中 W-S2 不等于允许正式提交；先完成 Task 8—9。

### Task 8：执行来源核验和两份真实文件 dry-run

**文件：**

- 修改：`tests/integration/pipeline/test_ws2_batch.py`
- 新增：`tests/integration/pipeline/test_ws2_batch_report_real.py`
- 生成但不提交：`data/manifests/legal_ingestion_batches/<batch_id>/` 下的 dry-run 报告

**步骤 1：来源只读核验。**

**命令执行意图：** 核对清单、真实路径、双轴分类和源摘要，不进行正文处理或提交。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S2 --verify-source-only
```

**预期输出：** `selected=2`、`failed=0`；两份源文件摘要与读取前一致。若 selected 不是 2，停止执行。

**步骤 2：正式路径 dry-run。**

**命令执行意图：** 用真实 CLI 走完整提取、S2 边界、结构化、切块和质量 v2，但不调用 Append-Only commit。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S2 --dry-run
```

**预期输出：** `selected=2`、`committed=0`、`auto_passed=2`、`review_required=0`、`failed=0`、`unsupported=0`；输出唯一 batch_report 路径。

**步骤 3：检查报告内容。**

集成测试读取当次报告并断言：

- 两个 source item 都有独立 source_sha256、document_id、quality report 和 disposition；
- quality ruleset 为 v2，两个 S2 gate 和所有通用 gate PASS；
- dry_run 明确为 true，commit result 为空；
- 报告不复制前置发布材料全文；
- 正式 normalized、structured、chunks、索引和 manifest 摘要前后不变。

**命令执行意图：** 自动验证 dry-run 报告和零正式写入，而不是只人工阅读控制台。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws2_batch.py tests/integration/pipeline/test_ws2_batch_report_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed。

**Checkpoint：** dry-run 通过只说明两份文件具备提交资格，尚未证明真实事务、回滚和检索有效。

### Task 9：在临时目录完成 Append-Only、失败隔离和检索回归

**文件：**

- 新增：`tests/integration/pipeline/test_ws2_qualified_incremental_import.py`
- 修改：`tests/unit/services/test_retriever.py`
- 按发现问题最小修改：现有 Append-Only 服务测试；不得先重写事务

**步骤 1：先写临时提交测试。**

测试在 `tmp_path` 复制最小基线数据和索引，对 2 份真实 W-S2 逐文件提交，断言：

- committed=2；
- document 数增加 2；
- normalized、structured、chunks 和 manifest 各增加对应两份记录；
- 关键词 chunk 与 FAISS 向量增加量等于本次生成 chunk 总数；
- FAISS 维度和模型标识不变；
- 两份结构化文档分别 32、37 条；
- 关键词和向量查询都能命中每份文件的独有条文；
- manifest 中 source_sha256、artifact digests、quality digest 和 batch_id 可追溯。

测试只断言“增量关系”，不把计划编写时的正式总数写死。

**命令执行意图：** 先证明测试能发现尚未验证的 W-S2 提交与检索契约。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws2_qualified_incremental_import.py -q
```

**预期输出：** 首次因测试尚未完成或发现真实链路缺口而 FAIL；只能做最小修复。

**步骤 2：验证逐文件失败隔离。**

注入第二份文件的 staged digest 不一致，断言第一份可独立 committed，第二份 failed 且零产物；批次汇总为 committed=1/failed=1，不回滚第一份，也不把整个批次标成成功。

再注入索引发布失败，断言该文件语料、索引和 manifest 全部回滚到提交前摘要。

**步骤 3：运行 W-S1 与完整回归。**

**命令执行意图：** 验证 S2 元数据和 CLI 改动没有影响已正式完成的 W-S1。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws2_qualified_incremental_import.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/unit/services/test_retriever.py -q
```

**预期输出：** 全部 PASS；W-S1 真实 8 文件和既有检索行为稳定。

**命令执行意图：** 在正式写入前运行仓库完整测试。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；无新增 warning、skip 或 xfail。任何失败都阻止 Task 10。

### Task 10：正式导入 2 份 W-S2 并同步状态

**文件：**

- 修改或新增：正式 `data/normalized/`、`data/structured/`、`data/chunks/` 对应产物
- 修改：正式关键词索引、FAISS 索引和增量 manifest
- 新增：`data/manifests/legal_ingestion_batches/<batch_id>/` 正式批次报告
- 新增：`tests/integration/pipeline/test_ws2_formal_index_state.py`
- 修改：`docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md`
- 修改：`README.md`
- 必要时修改：`docs/system_meta/文档索引.md`、`docs/system_meta/文档读取规则.md`

**步骤 1：建立正式写入前基线。**

记录并保存：

- `git status --short`，区分用户已有改动；
- 两份源 SHA-256；
- 当前 document、keyword chunk、FAISS vector 和 manifest 数量；
- FAISS 维度与模型标识；
- 8 份 W-S1 可检索证据；
- Task 8 通过的 batch report 路径和摘要。

工作区有无法避开的无关改动、正式索引数量不一致或源摘要变化时，立即停止，不执行正式导入。

**步骤 2：只执行一次正式命令。**

**命令执行意图：** 通过唯一 CLI 对清单中的 2 份 W-S2 逐文件执行质量资格和 Append-Only 正式提交。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --source-root 法律文本/todo --extraction-class W --content-class S2
```

**预期输出：** 新 batch_id；`selected=2`、`committed=2`、`auto_passed=0`、`review_required=0`、`failed=0`、`unsupported=0`。若任一文件失败，不重复整批命令，先根据单文件报告调查。

**步骤 3：验证正式状态。**

`test_ws2_formal_index_state.py` 必须读取正式产物，断言：

- 两个 document_id 在 normalized、structured、chunks、关键词索引、FAISS 映射和 manifest 中各出现一次；
- 正式增量相对步骤 1 为 document +2，chunk/vector +本次 chunk 数，manifest +2；
- 两份质量报告均为 v2 PASS；
- 真实检索能分别命中第 32 条和第 37 条附近的独有内容；
- W-S1 8 份文档仍存在、可检索，索引总量没有减少；
- 重复源摘要没有产生第二条正式 manifest。

**命令执行意图：** 验证“控制台显示 committed=2”与所有正式存储事实一致。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws2_formal_index_state.py tests/unit/services/test_retriever.py -q
```

**预期输出：** 全部 PASS；正式语料、两类索引和 manifest 一致。

**步骤 4：同步路线图和入口。**

仅在步骤 2—3 全部成功后：

- 把 S2 和 W-S2 里程碑更新为 `implemented`；
- 把 14 文件验收进度更新为 10/14，剩余 1 份 W-S3 和 3 份 PDF；
- 写入真实 batch_id、最终数量、测试结果和 commit 证据；
- README 将 W-S2 命令从“计划用法”更新为“已支持用法”；
- 若计划执行中新增、移动或重命名文档，同步索引、读取规则和所有入口链接。

若正式提交未全成功，路线图只能标记 `in_progress` 并如实记录每份状态，禁止写成 implemented。

**步骤 5：最终回归与提交。**

**命令执行意图：** 在文档状态同步后重新执行完整回归。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；正式索引状态测试包含在收集结果中。

确认 `git diff --cached` 只包含本 Phase 的代码、测试、文档和两份 W-S2 正式产物后，按总计划执行中文 commit；不得 push。

## 2. 分卷完成检查

分卷完成必须同时具备：

- 旧 W-S1 命令兼容，显式 W-S2 命令只选择 2 项；
- verify-source-only 和 dry-run 结果正确；
- 临时提交、失败隔离、回滚和两类检索通过；
- 正式 batch 为 committed=2；
- 正式语料、关键词索引、FAISS、manifest 和质量报告一致；
- W-S1 真实回归和仓库完整测试通过；
- 路线图只依据真实结果更新。

只完成 CLI 参数或 dry-run，不得执行 Phase commit，也不得把 W-S2 标记完成。
