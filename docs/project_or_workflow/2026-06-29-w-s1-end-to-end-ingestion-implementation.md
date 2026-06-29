# W-S1 端到端摄取 Implementation Plan

> 本计划用于在当前工作区直接按批次执行。

**目标：** 让评估基线中的 8 份 W-S1 法规从只读源文件经过可信 Word 提取、S1 正文边界、结构解析、质量门禁和现有单文件 Append-Only 链路，在临时验收环境中逐文件提交并可检索。

**架构：** 保留 `scripts/import_new_corpus.py` 作为唯一薄 CLI，使其委托统一摄取编排器。编排器分别路由 W 提取策略与 S1 边界策略，形成质量资格后复用既有 staging、两次 preflight、索引追加、回滚与 manifest；不新增按分类组合命名的入口。

**技术栈：** Python 3.14、标准库、现有 FastAPI/Pydantic/SQLite/FAISS 代码、macOS `/usr/bin/file` 与 `/usr/bin/textutil`、pytest；所有代码和测试必须使用 conda 环境 `fire`。

---

## 1. 计划地位与权威依据

本文是“W-S1 端到端摄取”里程碑的可执行入口，角色为 `project_or_workflow`。它不新增架构决策；冲突时按仓库既有优先级服从：

1. [法规摄取总体架构入口](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)；
2. [统一法规摄取入口 ADR](../architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)；
3. [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)；
4. [工程技术标准](../architecture_or_strategy/工程技术标准.md)与四篇专项设计；
5. [todo 法律语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)；
6. [显式新法规 Append-Only 增量导入计划](./2026-04-29-append-only-incremental-corpus-import.md)及当前代码。

## 2. 里程碑范围

### 2.1 纳入范围

W-S1 是双轴分类组合：

- `W`：真实签名证明为 DOC/DOCX，且 Word 转换候选可用；
- `S1`：文件主体只有一个目标法规，能够由唯一标题和连续条文块确认正文首尾。

唯一 14 文件评估基线中，W-S1 视图应恰好包含：

1. `事故调查、问责与系统治理/安全生产行政执法与刑事司法衔接工作办法.doc`；
2. `事故调查、问责与系统治理/河北省消防安全领域信用管理暂行细则.doc`；
3. `事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx`；
4. `督察、处罚与监管/中华人民共和国消防救援衔条例.docx`；
5. `督察、处罚与监管/河北省消防技术服务监督管理规定.doc`；
6. `督察、处罚与监管/河北省消防行政执法裁量实施办法.doc`；
7. `督察、处罚与监管/消防产品监督管理规定.doc`；
8. `督察、处罚与监管/消防监督检查规定.doc`。

该列表只用于计划说明。测试和实现必须从唯一 14 文件 fixture 按分类筛选，不得再维护第二份独立路径清单。

### 2.2 不纳入范围

- S2 复合发布、S3 正文后排除和 S4 混合不确定；
- PT 文本型 PDF、PS 扫描型 PDF、PX 异常混合类型；
- OCR 引擎、中文语言资源或 PDF 新依赖选型与安装；
- 旧法规覆盖、替换、条文级 diff 或语义去重；
- 8 文件全局事务、并行修改共享索引或跨进程锁；
- 修改或移动 `法律文本/todo/`、`法律文本/done/`；
- 绕过现有 Append-Only preflight、staging、回滚或 manifest。
- 为 W-S1、W-S2、PT-S1 等分类组合新增独立 CLI 或组合策略。

完成本里程碑不等于完成“多格式摄取分卷一”。本计划只对 11 份 Word 执行真实格式探测并处理其中 8 份 W-S1；fixture 中的 PDF 预期分类只用于保持唯一 14 文件基线完整，不替代 PDF 页级探针或 OCR 验证。

## 3. 全局阶段输入检查

### 已确认

- 现有增量导入已经支持显式单个全新 `.doc/.docx`、staging、索引副本、两次 preflight、回滚和 manifest。
- 当前缺口位于正式提交上游：真实类型证据、候选提取证据、S1 正文边界、跨层一致性和提交资格。
- 现有位置参数与 `--source` 语法保持兼容，但提交行为收紧；新增显式批次参数必须与单文件参数互斥。
- 原始 `法律文本/` 只读，所有真实验证必须校验运行前后 SHA-256 不变。
- 新增或修改测试必须遵循红测、最小实现、绿测、真实上游验证。
- 每份计划文档以 420 行为警戒线，禁止超过仓库 500 行硬上限。

### 缺失输入

- 无需为 W-S1 安装新依赖。
- 若 conda 环境 `fire`、`/usr/bin/file` 或 `/usr/bin/textutil` 不可用，Phase 1 必须停止。
- 若真实 14 文件集合或摘要与评估基线不一致，先更新或确认唯一基线，不得直接实现。

### 允许的默认值

- 来源摘要使用 SHA-256。
- 路径使用相对 `法律文本/todo/` 的 POSIX 表示并稳定排序。
- Word 无可靠真实分页时使用逻辑页和块顺序，明确记录 warning，不伪造页码。
- 真实提交验收使用 pytest 临时 `data_dir` 与 `FakeEmbedder`，不写仓库正式 `data/`。

## 4. 依赖与包管理工具

| 环境 | 包管理工具 | 本里程碑结论 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；Python 包只能使用该环境内的 `python -m pip` | 无需新增依赖，不执行安装 |
| Word 系统工具 | 现有 `/usr/bin/file`、`/usr/bin/textutil` | 只做可用性审计，不安装 |
| 前端 | 不涉及 | 不使用 npm、pnpm、yarn |
| 其他运行环境 | 不涉及 | 不安装 |

如实施中发现必须新增依赖，立即停止当前 Task，向用户列出依赖名、版本范围、用途、安装位置、包管理工具、许可证和替代方案；未经批准不得安装。

## 5. 分卷导航与职责

- [分卷一：统一编排契约、范围冻结与策略注册](./2026-06-29-w-s1-end-to-end-ingestion-implementation-part-1.md)
- [分卷二：W 提取策略、S1 边界策略与解析适配](./2026-06-29-w-s1-end-to-end-ingestion-implementation-part-2.md)
- [分卷三：质量资格、统一 CLI 与 Append-Only 接入](./2026-06-29-w-s1-end-to-end-ingestion-implementation-part-3.md)
- [分卷四：8 份真实文档验收、检索闭环与文档收尾](./2026-06-29-w-s1-end-to-end-ingestion-implementation-part-4.md)

默认读取顺序为：本总览 → 当前分卷 → 当前 Task 指定的专项设计、代码和测试。不得为执行单个 Task 加载其他无关分卷。

## 6. 执行顺序

1. 分卷一 Task 1—4：冻结唯一输入，固定统一编排器、独立策略注册和稳定状态语义。
2. 分卷二 Task 5—7：分别实现 W 提取策略、S1 边界策略及解析/chunk 适配。
3. 分卷三 Task 8—11：实现质量资格，升级唯一 CLI，并使旧服务入口委托统一编排器。
4. 分卷四 Task 12—14：完成 8 份真实文件质量验收、临时提交、检索闭环和文档审计。

不得跳过前一分卷 checkpoint 直接修改正式提交入口。每个 Task 必须先检查该阶段的已确认输入、缺失输入和默认值。

## 7. 全局硬门禁

1. 所有 Python、pytest、脚本和服务命令使用 `conda run -n fire ...`。
2. 每个 Task 显式写明后端、前端和其他运行环境的包管理工具及依赖结论。
3. 每条计划内命令必须说明执行意图和预期输出，不写包含几十行代码的终端命令。
4. 原始 `法律文本/` 只读；不得移动、重命名或改写源文件。
5. 整份候选提取文本只允许在进程内短暂存在；持久化从已确认的目标正文开始。
6. `boundary.status != confirmed` 时禁止生成正式 structured、chunks 或提交资格。
7. PAGE 域、页眉页脚、印发信息、条文串入、重复条文和跨层不一致必须阻断自动提交。
8. W-S1 新链路只有绑定源摘要、质量报告摘要和三类 staged 产物摘要的资格可以进入 commit。
9. 现有两次 preflight、索引副本、独占发布、回滚和 manifest 最后写入顺序不得改变。
10. 真实 8 文件测试不得使用 `skip`、`xfail` 或“文件不存在则返回”。
11. 单份失败不得降低其他文件门禁，也不得破坏其他已提交文件。
12. 所有真实提交测试使用临时目录，不写仓库正式 `data/`。
13. `unsupported`、`review_required`、`failed` 必须分离；任何非合格状态均零正式写入。

## 8. Git 策略

- 本计划授权实施阶段在每个完整 Phase 通过单元测试、相关回归和真实上游验证后执行一次 `git add` 与 `git commit`。
- commit 说明必须使用中文，只包含该 Phase 已验证的改动。
- 工作区存在非代理产生的改动时必须避开；无法安全避开则停止提交并报告。
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写操作。
- 当前计划编写任务不执行 commit。

## 9. 分卷完成定义

### 分卷一

- 唯一 14 文件 fixture 与当前 `todo/` 一致；
- W-S1 派生视图恰好 8 项；
- 来源、真实类型、双轴候选和分类证据可机器读取；
- 统一编排器只按独立提取轴和内容轴选择策略，不注册 W-S1 组合策略；
- 共同提取协议不持久化整份候选正文；
- 既有增量导入事务边界被测试固定。

### 分卷二

- DOC/DOCX 可形成保留行序与来源位置的内存候选；
- 8 份 W-S1 均能唯一确认标题、第一条和正文结束位置；
- 合法 `LegalDocumentIntermediate` 只含目标法规正文；
- `confirmed` 正文可适配现有 `ParsedDocument` 和 chunks；
- 不确定边界在生成持久化产物前停止。

### 分卷三

- 通用与 Word 专属门禁覆盖当前已知风险；
- 每份文件具有独立状态历史和原子质量报告；
- `CommitQualification` 与源、报告和 staged 产物摘要绑定；
- 未合格文件不能调用正式 commit；
- 唯一 CLI 支持兼容单文件语法和互斥的显式批次模式；
- `run_incremental_import()` 委托统一编排器，不保留服务层旁路；
- 现有 Append-Only 回滚与 manifest 顺序无回归。

### 分卷四

- 8 份真实 W-S1 文件均通过无 skip 的质量矩阵；
- 全部文件在临时验收环境逐文件达到 `committed`；
- normalized、structured、chunks、两类索引与 manifest 一致；
- 每条目标条文可检索，源文件摘要不变；
- README、工程技术标准、文档索引和读取规则与实现同步。

## 10. 里程碑完成定义

只有同时满足下列条件，才可把“W-S1 端到端摄取”标记完成：

1. Task 1—14 的 checkpoint 均有实际测试证据；
2. 8 份文件全部达到 `committed`，不能以 `completed_with_exceptions` 替代；
3. 所有真实测试无 skipped/xfailed；
4. 自动通过项无未解释 warning；
5. 源文件运行前后 SHA-256 完全一致；
6. 仓库正式 `data/` 未被测试污染；
7. 现有单文件 Append-Only 冲突、回滚、索引和 manifest 行为无回归；
8. 文档系统已登记并能按总览与当前分卷最小读取。

## 11. 总体验收命令

**命令执行意图：** 验证五份计划文档均低于 420 行警戒线。

```bash
wc -l docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation*.md
```

**预期输出：** 总览和四个分卷均不超过 420 行。

**命令执行意图：** 在实现完成后汇总执行 W-S1 单元、集成和真实验收测试。

```bash
conda run -n fire python -m pytest tests/unit/services tests/integration/pipeline -q
```

**预期输出：** 全部相关测试 PASS，真实 W-S1 测试无 skipped/xfailed。

**命令执行意图：** 在里程碑关闭前运行仓库完整回归。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；任何新增失败必须修复，不能归入历史例外。
