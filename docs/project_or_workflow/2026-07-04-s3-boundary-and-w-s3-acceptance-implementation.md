# S3 边界能力与 W-S3 组合验收实施计划（已完成）

> **执行状态：** Task 1—8 已全部完成；S3 与 W-S3 状态为 `implemented`。本文及两个分卷保留为可追溯执行记录，不表示仍待编码。

**目标：** 在复用现有 W 提取、统一编排、质量资格和 Append-Only 提交能力的前提下，实现可独立复用的 S3 正文后排除策略，并让唯一 W-S3 真实法规以 29 条纯净正文安全进入正式索引。

**架构：** 运行时继续按“提取轴 + 内容轴”分别选择策略。S3 先确认唯一目标标题和连续正文，再用实质尾部强信号与辅助信号识别印发信息、附件目录、文书模板、评分表和页码域，只保留排除范围的位置、类型与原因。W-S3 只是清单筛选和真实验收组合，不新增组合策略、专用服务或第二个 CLI。

**技术栈：** Python 3.14、标准库 `dataclasses`/`re`、pytest、现有 Word `textutil` 提取链路、现有 Append-Only 提交、关键词检索与 `faiss-cpu==1.14.3`；全部 Python 命令通过 conda 环境 `fire` 执行。

---

## 1. 计划地位与权威依据

本文是“S3 边界能力与 W-S3 组合验收”里程碑的可执行入口，角色为 `project_or_workflow`。它不替代设计；冲突时依次服从：

1. 根目录 `AGENTS.md`；
2. [工程技术标准](../architecture_or_strategy/工程技术标准.md)；
3. [法规摄取总体架构](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)；
4. [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)；
5. [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)；
6. [S3 正文后排除边界专项设计](../architecture_or_strategy/2026-07-04-s3-trailing-exclusion-boundary-design.md)；
7. [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)；
8. 本计划及其当前分卷。

真实样本事实来自 [todo 法律语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)。W-S1、W-S2 计划只用于核对已实现公共主干，不得复制形成第三套入口或提交事务。

## 2. 当前状态

| 项目 | 当前事实 |
| --- | --- |
| W 提取、统一编排和 Append-Only | `implemented`，由 W-S1/W-S2/W-S3 验收 |
| S1、S2 | `implemented` |
| S3 | `implemented`；独立策略、v3 门禁、临时事务和正式索引验收均已完成 |
| Linear 里程碑 | “消防AI”项目下“W-S3 尾部排除内容”正文已标记“已完成 / implemented”；因未关联 issue，数值 `progress` 仍显示 0，不作为能力状态依据 |
| W-S3 真实文件 | `督察、处罚与监管/河北省消防救援机构执法过错责任追究规定.doc` |
| 正文事实 | 第一条至第二十九条 |
| 排除结果 | 印发信息、附件目录、5 套文书模板和页码域未进入正文或 chunks |
| chunk 结果 | 旧探针 37 个且包含污染；正式验收冻结为 34 个干净 chunks |

完成证据为正式批次 `c132d0f3-aa52-40cc-a1c8-7e26cb0209e1`（`selected=1`、`committed=1`、`failed=0`）、20 份正式文档、876 个关键词 chunks、876 个 FAISS 向量、14 条 manifest 记录，以及仓库完整回归 471 项通过。Task 1—8 对应提交从 `6ca5d00` 至 `f184086`，均已落入当前 Git 历史。

## 3. 里程碑范围

### 3.1 纳入范围

- 从唯一 14 文件 fixture 派生恰好 1 项 W-S3 视图；
- 核对本阶段实际使用的 Python 3.14 与 pytest 官方契约；
- 在测试保护下抽取 S1/S2/S3 共用的纯边界辅助函数；
- 新增独立 `S3BoundaryStrategy`；
- 独立注册 S3 并接入统一编排器；
- 增加 S3 尾部存在、位置、覆盖和输出纯净门禁；
- 把质量规则集升级为 `legal-quality-v3`；
- 完成真实 W-S3 来源核验、dry-run、临时提交、回滚和检索验收；
- 只在全部门禁通过后正式提交唯一 W-S3 文件；
- 同步路线图、README、文档系统和 Linear 里程碑状态。

### 3.2 不纳入范围

- 不实现 PT、PS、OCR 或 PS-S3；
- 不实现 S4 人工复核工作台；
- 不新增 `W-S3` 组合策略、组合服务或专用 CLI；
- 不重写分类器、Append-Only 事务、FAISS 格式或检索算法；
- 不把正文中的“附件”“审批表”“决定书”等词当作无条件截断点；
- 不保存附件、模板、评分表或其他排除内容的标题、摘要和正文副本；
- 不把旧探针的 37 个污染 chunks 写成新验收目标；
- 不修改、移动或重命名 `法律文本/todo/` 源文件。

## 4. 全局阶段输入检查（已收口）

### 已确认

- S3 专项设计已批准，强信号、辅助信号、排除类型和安全停止规则明确；
- 唯一 W-S3 文件存在，冻结基线记录 `W + S3` 和 29 条正文；
- CLI 已支持通用 `--extraction-class` 与 `--content-class`，无需新增 S3 专用参数；
- W 提取、结构解析、切块、质量资格、逐文件提交和回滚均可复用；
- 现有 `ExcludedRange` 足以表达多个互不重叠的尾部范围，无需新增排除正文存储字段；
- 本里程碑无需新增依赖。
- Python 3.14、pytest、dataclasses、Enum 和 `tmp_path` 契约已经核验并记录；
- 干净 chunk 数已冻结为 34；
- 正式批次、源摘要、索引和 manifest 数量已经由 Task 8 固定并验证。

### 已补齐的输入

- 官方运行时契约核验记录：`docs/reference_material/2026-07-04-s3-runtime-contract-verification.md`；
- Task 6/7 冻结 29 条正文和 34 个干净 chunks；
- Task 8 固定正式批次、源摘要、20/876/876 索引数量和 14 条 manifest 记录；
- 真实尾部块均被现有设计解释，无需放宽门禁。

当前没有遗留的 W-S3 阶段输入缺口；后续 PT、PS/OCR 属于独立里程碑，不应回填到本计划。

### 允许的默认值

- 标题、正文结束、尾部起点或尾部类型不唯一时返回 `review_required`；
- 来源摘要变化、块顺序非法、范围重叠或跨层污染返回 `failed/rejected`；
- 只有页码或普通印发尾注、没有实质尾部强信号时不得自动确认为 S3；
- 尾部标记后再次出现正式条文时按 S4 风险处理，零正式写入；
- 规则集升级到 `legal-quality-v3`，S1/S2 算法不随版本号升级而改变；
- 所有真实测试缺文件即失败，禁止 `skip`、`xfail` 或提前返回。

## 5. 依赖与包管理工具

| 环境 | 包管理工具 | 本里程碑处理 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；如获批才可使用 conda 或 `conda run -n fire python -m pip` | 无需新增依赖，禁止自行安装 |
| 前端 | 不涉及；不运行 npm、pnpm 或 yarn | 无前端改动 |
| 系统工具 | macOS 自带 `/usr/bin/textutil`，由现有 W 提取器调用 | 只读复用，不安装、不替换 |
| 联网核验 | Firecrawl、Exa 或 Tavily MCP | 只查官方文档，不使用其他通用搜索/抓取工具 |
| 数据与索引 | 现有 CLI、关键词索引和 `faiss-cpu==1.14.3` | 不改索引格式，不新增模型依赖 |

执行中若发现必须新增依赖，应立即停止，列出依赖名称、用途、版本范围、安装位置和包管理工具，待用户确认后再修改计划并继续。

## 6. 分卷导航

| 分卷 | Task | 负责内容 | 正式写入 |
| --- | --- | --- | --- |
| [分卷一](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation-part-1.md) | Task 1—5 | 冻结 W-S3 事实、核验官方契约、抽取公共函数、实现与注册 S3、增加 v3 门禁 | 禁止 |
| [分卷二](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation-part-2.md) | Task 6—8 | 真实预演、临时 Append-Only、回滚、正式导入、检索和状态收口 | 仅 Task 8 |

## 7. 执行顺序

1. 严格按分卷一 → 分卷二执行；
2. 每个 Task 开始前重新检查其输入、缺失项和依赖结论；
3. 每个行为变化先写失败测试，确认测试因目标能力缺失而失败，再做最小实现；
4. Task 1—5 只允许只读源文件和 pytest 临时目录；
5. Task 6 允许生成 dry-run 批次报告，但不得调用正式提交；
6. Task 7 只能在 `tmp_path` 或显式临时数据目录验证提交、回滚和检索；
7. Task 8 是唯一允许修改正式 `data/` 的 Task；
8. 正式导入后必须核对语料、关键词索引、FAISS、manifest、质量报告和检索，不能只看控制台 `committed=1`。

## 8. 全局硬门禁

1. W-S3 只能从唯一 `todo_baseline.json` 动态筛选，禁止建立第二份同义清单；
2. 运行时只能注册独立 `ContentClass.S3`，禁止 `W-S3` 策略键；
3. 必须先确认标题、第一条、连续条号和最后一条，再识别尾部；
4. 正文内引用附件或文书名称不得触发截断；
5. S3 至少需要一个实质尾部强信号，普通页脚和页码不足以确认；
6. 候选尾部起点后的所有非空块必须被解释；未知块进入复核；
7. 尾部起点后出现正式条文时进入 S4 风险；
8. 排除范围必须位于正文之后，按来源位置递增、互不重叠；
9. 排除范围只记录位置、类型和原因，不保存排除正文；
10. normalized、structured、chunks、诊断和报告不得复制排除内容；
11. parsed articles 必须恰好为第一条至第二十九条；
12. 非 `confirmed` 边界不得生成资格或正式产物；
13. 真实测试不得使用 skip、xfail 或文件缺失时 return；
14. W-S1 8 份、W-S2 2 份真实回归必须保持通过；
15. 禁止改变现有 Append-Only 发布顺序、FAISS 维度和模型标识。

## 9. Git 策略

本计划授权未来实施阶段在每个 Task 完成全部规定测试和真实验证后执行一次 `git add` 与 `git commit`：

| Task | 中文 commit 说明 |
| --- | --- |
| Task 1 | `冻结W-S3范围并核验运行时契约` |
| Task 2 | `重构法规边界公共辅助函数` |
| Task 3 | `实现S3正文后排除边界` |
| Task 4 | `接入S3独立策略路由` |
| Task 5 | `增加S3专属质量门禁` |
| Task 6 | `完成W-S3真实预演验收` |
| Task 7 | `验证W-S3临时提交与回滚` |
| Task 8 | `完成W-S3正式导入与状态同步` |

- 每次提交只能包含当前 Task 已验证的代码、测试、文档或正式产物；
- 提交前必须检查 `git diff --cached`，避开用户已有改动；
- 无法安全拆分用户改动时停止提交并报告；
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写；
- 本表中的 Task commit 已全部完成；后续文档勘误按新的当前任务授权处理，不复用本表重复提交业务改动。

## 10. 里程碑完成定义

以下完成条件已全部满足，因此 S3 和 W-S3 已标记为 `implemented`：

- S3 独立注册，S1/S2 行为和 S4 安全状态不变；
- 唯一 W-S3 文件形成 `confirmed` 中间格式；
- structured 恰好包含第一条至第二十九条；
- 第二十九条仅包含正式终止条款；
- 印发信息、附件目录、5 套模板和页码域均被排除且不被持久化；
- 四项 S3 专属门禁及全部通用门禁通过，规则集为 v3；
- dry-run 为 `selected=1`、`auto_passed=1`，无复核、失败或不支持；
- 临时提交、摘要失败、索引发布失败和 manifest 失败回滚均通过；
- 正式语料、两类索引、manifest、质量报告和真实检索一致；
- W-S1、W-S2 真实回归及仓库完整测试通过；
- 路线图、README、文档索引、读取规则和 Linear 状态与真实证据一致。

计划写完、单元测试通过或 dry-run 通过都不能单独视为里程碑完成；本次状态以正式写入、真实索引、回归测试和 Linear 完成总结的组合证据为准。

## 11. 总体验收命令

**命令执行意图：** 汇总运行 S3 单元测试、W-S3 真实验收和 W-S1/W-S2 回归。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_boundary_common.py tests/unit/services/test_legal_s3_boundary.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_todo_ws3_scope.py tests/integration/pipeline/test_ws3_ingestion_real.py tests/integration/pipeline/test_ws3_legal_corpus_quality.py tests/integration/pipeline/test_ws3_batch.py tests/integration/pipeline/test_ws3_batch_report_real.py tests/integration/pipeline/test_ws3_qualified_incremental_import.py tests/integration/pipeline/test_ws3_formal_index_state.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；W-S1、W-S2、W-S3 真实测试均无 skipped/xfailed。

**命令执行意图：** 最终运行仓库完整回归，发现计划范围外的兼容性破坏。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部测试 PASS；测试数量可以随新增测试增加，但不得少收集既有测试，也不得新增 warning、skip 或 xfail。
