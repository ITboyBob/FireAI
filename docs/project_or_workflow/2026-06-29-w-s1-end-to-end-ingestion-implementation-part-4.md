# W-S1 端到端摄取实施计划（分卷四）

> 本计划用于在当前工作区直接按批次执行。

**目标：** 使用唯一真实基线中的 8 份 W-S1 法规，完成逐文件质量验收、临时目录内的 Append-Only 提交验证、检索一致性验证和文档收尾。

**架构：** 本卷只消费分卷一至三已经固定的 W-S1 来源记录、`confirmed` 中间格式、质量报告和提交资格。真实验收复用现有单文件 staging、两次 preflight、索引追加、回滚和 manifest，不建立 8 文件全局事务，也不直接修改正式 `data/`。

**技术栈：** Python 3.14、pytest、现有 SQLite/FAISS 索引、`FakeEmbedder`、macOS `/usr/bin/textutil`；所有代码和测试命令均在 conda 环境 `fire` 中执行。

---

## 1. 导航与权威依据

- [W-S1 实施计划总览](./2026-06-29-w-s1-end-to-end-ingestion-implementation.md)
- [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)
- [法规摄取总体架构入口](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)
- [统一法规摄取入口 ADR](../architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)
- [多格式法律语料摄取总设计](../architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [todo 法律语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)
- [显式新法规 Append-Only 增量导入计划](./2026-04-29-append-only-incremental-corpus-import.md)
- [工程技术标准](../architecture_or_strategy/工程技术标准.md)

本文覆盖 Task 12—14。逐文件风险结论以评估基线和质量门禁设计为准；本文不得创建第二份独立维护的 8 文件路径清单。

## 2. Phase 4 启动输入检查

### 已确认

- 分卷一的唯一 14 文件 fixture 已冻结，W-S1 视图通过 `extraction_class=W` 与 `content_class=S1` 派生为 8 份文件。
- 分卷二已经为 W-S1 生成合法 `LegalDocumentIntermediate`，且只有 `boundary.status=confirmed` 才能产生 structured 和 chunks。
- 分卷三已经生成逐文件质量报告、合法状态和 `CommitQualification`。
- 唯一 CLI 与兼容服务入口均已委托统一编排器，不存在绕过资格的正式提交旁路。
- 现有 Append-Only 链路继续负责 staging、两次 preflight、索引副本、独占发布、回滚和 manifest 最后写入。
- 原始 `法律文本/` 全程只读；真实验收只能向 pytest 的临时目录写产物。

### 缺失输入

- 分卷一至三任一 checkpoint 未通过时不得开始本卷。
- 8 份 W-S1 真实源文件任一缺失、类型变化或 SHA-256 与冻结输入不一致时，本卷必须失败并列出差异。
- 编码前必须使用 Firecrawl、Exa 或 Tavily 核对 Python 3.14、pytest、SQLite 与当前 FAISS API 的最新官方文档；未留下核对记录时停止 Task 12。
- 若本机 `/usr/bin/textutil` 不可执行，停止真实验收，不得改用未经批准的替代工具。

### 允许的默认值

- 使用现有 `tests.integration.pipeline.test_build_pipeline.FakeEmbedder`，避免真实模型下载和向量波动。
- 每份 W-S1 文件拥有独立 attempt、staging、质量报告和 commit 结果。
- 一份文件失败不阻止质量检查继续收集其他文件结果，但失败文件不得进入 commit。
- 所有正式产物断言都针对 pytest 临时 `data_dir`；不写仓库真实 `data/`。

### 依赖与包管理工具

- 本卷无需新增依赖，沿用 conda 环境 `fire` 中已有 Python 包和 pytest。
- 后端包管理工具为 conda `fire` 环境内的 pip，但本卷不执行安装。
- 前端不涉及，npm、pnpm、yarn 均不使用。
- 其他运行环境不涉及；`/usr/bin/textutil` 只作为现有系统工具调用。

## Task 12：建立 W-S1 真实质量验收矩阵

**Files：**

- Create: `tests/integration/pipeline/test_ws1_legal_corpus_quality.py`
- Modify: `tests/integration/pipeline/test_incremental_import_real_smoke.py`
- Read: `tests/fixtures/legal_ingestion/todo_baseline.json`
- Read: `docs/reference_material/2026-06-28-todo-legal-corpus-assessment.md`
- Read: `docs/architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md`

**依赖：** 无需新增依赖；使用 conda 环境 `fire` 中的 pytest。前端和其他运行环境 N/A。

### Step 1：检查本 Task 输入

- 已确认：8 份 W-S1 文件必须从唯一 14 文件 fixture 派生，不在测试中复制路径清单。
- 缺失项：fixture 的分类、预期条数或风险码缺失时停止，不能在本卷创建第二套映射。
- 默认值：真实文件缺失直接失败；不允许 `skip`、`xfail` 或“缺失则返回”。

### Step 2：编写红测

参数化加载唯一 fixture，只选择 W-S1，并固定：

```python
cases = [
    item
    for item in load_todo_baseline()
    if item.expected_extraction_class == "W"
    and item.expected_content_class == "S1"
]
assert len(cases) == 8
```

每份文件必须执行完整的分类、提取、边界、解析、切块和质量门禁，并断言：

- 来源 SHA-256 在处理前后不变；
- `boundary.status == "confirmed"`；
- 目标标题唯一，第一条存在，条号连续、唯一且条文非空；
- `PAGE \* MERGEFORMAT`、`NUMPAGES`、HYPERLINK 指令、页眉页脚、孤立页码和印发尾注均未进入正文；
- intermediate、normalized、structured 和 chunks 的标题、条号、正文摘要及覆盖关系一致；
- 每条正文至少映射一个 chunk，且不存在正文范围外的 chunk；
- 自动通过的质量报告不存在未解释 warning。

逐文件额外断言：

| 文件 | 必测风险 |
| --- | --- |
| 安全生产行政执法与刑事司法衔接工作办法.doc | 第三十二条与第三十三条不得重复或互相串入 |
| 河北省消防安全领域信用管理暂行细则.doc | 第三十一条尾部无 PAGE 域 |
| 河北省火灾事故调查处理规定.docx | 27 条连续、非空、无污染 |
| 中华人民共和国消防救援衔条例.docx | 26 条连续、非空、无污染 |
| 河北省消防技术服务监督管理规定.doc | 第三十条尾部无页码域 |
| 河北省消防行政执法裁量实施办法.doc | 62 条连续，印发信息与 PAGE 域不进入第六十二条 |
| 消防产品监督管理规定.doc | 44 条连续，额外结构块不造成条文重复 |
| 消防监督检查规定.doc | 40 条连续，额外结构块不造成条文重复 |

旧 smoke 中“本机缺少真实文件则 skip”的行为必须删除，改为输出缺失相对路径并失败。

### Step 3：运行红测

**命令执行意图：** 证明当前链路尚不能对 8 份 W-S1 真实文件执行完整质量验收。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_incremental_import_real_smoke.py -q
```

**预期输出：** FAIL，首个失败指向尚未接线的 W-S1 上游、已知 PAGE 域、条文串入或旧 smoke 的 skip；不得把真实文件缺失显示为 skipped。

### Step 4：按失败类别执行最小修复

每轮只修复一个由真实样本证明的问题：

1. 先把真实失败固化为对应单元测试；
2. 只调整分类、提取、边界、清洗或门禁中的责任组件；
3. 不按文件名硬编码完整正文、条文内容或最终产物；
4. 合法条号例外必须记录来源证据；
5. 无法自动证明的阅读顺序或边界必须转 `review_required`，不能降低门禁。

### Step 5：运行绿测与回归

**命令执行意图：** 验证 8 份 W-S1 文件均形成可回溯的质量结论，且既有真实 smoke 不再静默跳过。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_incremental_import_real_smoke.py -q
```

**预期输出：** PASS；恰好收集 8 个 W-S1 case，无 skipped/xfailed，源文件摘要不变。

### Step 6：记录 checkpoint

- 8 份真实文件均有确定的质量状态和完整门禁报告；
- 已知 PAGE 域、条文串入、重复条文和尾部污染均被检出或修复；
- 只有全部门禁通过的文件获得提交资格；
- 仓库真实 `data/` 与 `法律文本/` 均未变化。

## Task 13：验证 W-S1 逐文件 Append-Only 提交与检索闭环

**Files：**

- Modify: `tests/integration/pipeline/test_ws1_qualified_incremental_import.py`
- Modify: `tests/integration/pipeline/test_incremental_import_pipeline.py`
- Modify: `tests/unit/services/test_retriever.py`
- Read: `app/services/incremental_import.py`
- Read: `app/services/keyword_index.py`
- Read: `app/services/vector_index.py`

**依赖：** 无需新增依赖；使用 conda `fire`、pytest、SQLite、现有 FAISS 能力和 `FakeEmbedder`。前端和其他运行环境 N/A。

### Step 1：检查本 Task 输入

- 已确认：Task 12 的 8 份质量报告全部可读取，合格文件具有内容绑定的 `CommitQualification`。
- 缺失项：任一文件仍是 `review_required` 或 `failed` 时，不得把“部分提交成功”写成里程碑完成。
- 默认值：8 份文件按 fixture 的稳定相对路径顺序逐文件提交；每份使用独立 run_id 和 staging。

### Step 2：编写红测

在 pytest 临时目录中先建立一份既有语料及索引，再逐文件执行 W-S1 协调入口，断言：

- 每次 commit 前重新验证源摘要、质量报告摘要和三类 staged 产物摘要；
- 只有 `auto_passed` 或重新机械门禁通过的 `review_passed` 才能提交；
- `unsupported`、`review_required`、`failed` 均零正式写入，并映射稳定错误码和退出码；
- normalized、structured、chunks、关键词索引、向量映射和 manifest 的 document_id 集合一致；
- 每条目标条文均可从关键词索引命中；
- 向量位置连续，数量与向量索引一致；
- 一份文件失败只回滚自身，不破坏此前成功文件；
- 重跑同一来源触发 append-only 冲突，正式产物完全不变；
- 8 次提交均复用现有两次 preflight、索引备份回滚和 manifest 最后写入顺序。

### Step 3：运行红测

**命令执行意图：** 证明当前单文件增量链路尚未消费 W-S1 质量资格，也未形成 8 文件逐文件调度闭环。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** FAIL，原因是质量资格、W-S1 协调入口或真实上游接线尚未完成；失败前不得写仓库正式 `data/`。

### Step 4：执行最小接线修复

- 复用分卷三的协调入口，按稳定顺序调用现有单文件 commit；
- 不在 CLI、`run_incremental_import()` 或其他服务函数中保留统一编排器旁路；
- 不绕过 `CommitQualification` 直接构造 `CommitPlan`；
- 保持 manifest 只记录完整 committed 事实；
- 故障注入只修改 pytest 临时产物，不修改真实源文件。

### Step 5：运行绿测和既有回归

**命令执行意图：** 验证 W-S1 端到端提交闭环，同时证明既有单文件事务语义未回归。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_qualified_incremental_import.py tests/integration/pipeline/test_incremental_import_pipeline.py tests/unit/services/test_incremental_import.py tests/unit/services/test_retriever.py -q
```

**预期输出：** PASS；8 份文件在临时 `data_dir` 中逐文件提交并可检索，重复导入和故障注入均在预期位置失败。

### Step 6：记录 checkpoint

- 8 份 W-S1 文件均达到 `committed`；
- 正式产物集合、两类索引与 manifest 一致；
- 单文件失败隔离、回滚和 append-only 冲突行为保持不变；
- 所有证据均来自临时目录，真实源文件摘要不变。

## Task 14：执行最终审计与文档同步

**Files：**

- Modify: `README.md`
- Modify: `docs/architecture_or_strategy/工程技术标准.md`
- Modify: `docs/system_meta/文档索引.md`
- Modify: `docs/system_meta/文档读取规则.md`
- Modify: `docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation.md`
- Create: `tests/unit/docs/test_ws1_plan_docs.py`
- Read: `scripts/import_new_corpus.py`

**依赖：** 无需新增依赖；文档检查使用现有 shell 工具，测试仍使用 conda `fire`。前端和其他运行环境 N/A。

### Step 1：检查本 Task 输入

- 已确认：Task 1—13 的 checkpoint 和真实测试结果均可核验。
- 缺失项：任一测试失败、skip、未解释 warning 或未提交文件存在时，停止收尾，不得把里程碑标记完成。
- 默认值：README 只更新运行入口和能力边界；工程规则写入工程技术标准；执行细节留在本计划。

### Step 2：编写文档契约红测

测试断言五份计划均不超过 420 行、所有相对 Markdown 链接存在、文档索引与读取规则登记三层结构、README 只展示统一 CLI、工程技术标准声明所有正式提交必须经过 `confirmed + qualified`。

### Step 3：运行红测

**命令执行意图：** 证明实现完成后的运行入口和工程规则尚未同步。

```bash
conda run -n fire python -m pytest tests/unit/docs/test_ws1_plan_docs.py -q
```

**预期输出：** FAIL，原因是 README 尚未说明统一 CLI 的单文件/批次模式，或工程技术标准尚无全局资格规则。

### Step 4：同步文档

- README 只保留 `scripts/import_new_corpus.py`，说明兼容单文件语法、互斥批次参数和行为收紧；
- 工程技术标准记录所有正式摄取必须经过统一编排器与 `confirmed + qualified`；
- 文档索引登记总体架构、ADR、能力路线图、W-S1 总览与四个分卷；
- 文档读取规则规定法规摄取任务先读能力路线图，再按需读取总体架构、当前计划和专项设计；
- 总览完成定义回填实际测试入口，不复制测试结果正文。

### Step 5：验证文档行数、链接与入口

**命令执行意图：** 以可返回非零退出码的测试检查 420 行上限、相对链接和文档入口。

```bash
conda run -n fire python -m pytest tests/unit/docs/test_ws1_plan_docs.py -q
```

**预期输出：** PASS；任一文件超过 420 行、链接缺失或入口未同步都会导致测试失败。

**命令执行意图：** 检查文档入口、W-S1 术语和命令环境声明均已同步。

```bash
rg -n "W-S1|conda run -n fire|无需新增依赖" README.md docs/system_meta docs/architecture_or_strategy/工程技术标准.md docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation*.md
```

**预期输出：** 总览、四个分卷、索引、读取规则和必要入口均有可解释命中，无旧路径或第二套清单声明。

### Step 6：运行 W-S1 汇总测试

**命令执行意图：** 汇总验证 W-S1 单元、集成、真实质量和临时提交闭环。

```bash
conda run -n fire python -m pytest tests/unit/services tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；若存在仓库既有例外，必须逐项证明与 W-S1 无关。

### Step 7：运行仓库完整回归

**命令执行意图：** 证明 W-S1 接线没有破坏全量建库、既有增量导入和在线检索。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；任何新增失败都必须修复，不能归为历史例外。

### Step 8：记录最终 checkpoint

- 8 份 W-S1 文件均有来源、分类、边界、门禁、提交和检索证据；
- 全部文件在临时验收环境达到 `committed`，真实源文件摘要不变；
- 现有单文件 Append-Only 事务语义未被重写；
- README、工程技术标准、文档索引和读取规则与实现一致；
- 本卷不授权 `git push`、历史改写或移动 `todo/done` 源文件。
