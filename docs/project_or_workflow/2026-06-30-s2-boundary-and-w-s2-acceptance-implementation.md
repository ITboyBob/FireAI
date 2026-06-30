# S2 边界能力与 W-S2 组合验收 Implementation Plan

> 本计划用于在当前工作区直接按分卷执行。当前任务只编写计划，不实现 S2。

**目标：** 在复用现有 W 提取、统一编排、质量资格和 Append-Only 提交能力的前提下，实现可独立复用的 S2 复合发布边界策略，并让评估基线中的 2 份 W-S2 真实法规安全进入正式索引。

**架构：** 运行时仍按“提取轴 + 内容轴”分别选择策略。S2 只负责识别目标法规之前的发布令、修改决定、签署机关和日期等前置材料，形成带来源位置的元数据证据，并确保这些材料不进入正文和 chunk。W-S2 只是清单筛选条件和真实验收组合，不新增组合策略、组合服务或第二个 CLI。

**技术栈：** Python 3.14、`dataclasses`、`argparse`、pytest、现有 Word `textutil` 提取链路、现有 Append-Only 摄取与 FAISS 检索链路；全部 Python 命令通过 conda 环境 `fire` 执行。

---

## 1. 计划地位与权威依据

本文是“S2 边界能力与 W-S2 组合验收”里程碑的可执行入口，角色为 `project_or_workflow`。它不替代架构设计；冲突时依次服从：

1. 根目录 `AGENTS.md`；
2. [工程技术标准](../architecture_or_strategy/工程技术标准.md)；
3. [法规摄取总体架构](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)；
4. [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)；
5. [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)；
6. [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)；
7. 本计划及其当前分卷。

真实样本事实来自 [todo 法规语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)。W-S1 计划只用于核对已实现公共主干，不是本里程碑的复制模板。

## 2. 里程碑范围

### 2.1 纳入范围

本里程碑新增一项能力、完成一个组合验收：

- 新能力：S2 复合发布边界策略；
- 复用能力：W 提取、统一编排器、通用质量资格、逐文件隔离和 Append-Only 提交；
- 组合验收：唯一 14 文件基线中 `expected_extraction_class=W` 且 `expected_content_class=S2` 的 2 份文件。

两份真实文件及硬验收事实如下：

| 文件 | S2 前置材料 | 目标正文 | 必须保留的元数据 | 必须排除的污染 |
| --- | --- | --- | --- | --- |
| `事故调查、问责与系统治理/河北省消防设施管理规定.docx` | 政府令、修改决定、`附件2`、修改条目说明 | 从第二十五个非空块的目标标题开始，连续第 1—32 条 | 发布机关、公布/修正日期、版本依据及来源位置 | 修改决定中的条号和“附件2”不得进入 32 条正文 |
| `事故调查、问责与系统治理/社会消防安全教育培训规定.doc` | 联合发布信息、九个签署机关、中文数字日期；标题在发布页和正文前各出现一次 | 选择紧邻连续第 1—37 条的后一个同名标题 | 联合发布机关、公布日期及来源位置 | 发布页同名标题、签署机关和日期不得进入 37 条正文 |

这里的“来源位置”是指元数据必须能指回 Word 提取结果中的具体块和字符范围，不能只保存一个无法审计的字符串。

### 2.2 不纳入范围

- 不实现 S3 附件/评分表/模板等正文后排除策略；
- 不实现 S4 人工复核工作台；
- 不实现 PT、PS 或 OCR；
- 不新建 `W-S2` 组合策略、组合注册表、组合服务或专用 CLI；
- 不修改现有 Append-Only 事务顺序、FAISS 索引格式或检索算法；
- 不把“前面出现附件”误当成正文结束信号；
- 不借 S2 改造重写 S1，除非共享模型扩展导致必要的兼容适配；
- 不在任何真实测试中修改 `法律文本/todo/` 源文件。

## 3. 全局阶段输入检查

### 已确认

- W 提取、统一编排、质量资格、逐文件隔离和 Append-Only 提交均已实现并通过 W-S1 验收；
- 两份 W-S2 源文件存在，唯一基线分别记录 32 条和 37 条；
- 两种真实结构已完成只读探测，足以覆盖“修改决定在前”和“联合发布信息在前”；
- S2 的架构职责、歧义状态和元数据证据要求已有批准设计；
- 当前 `faiss-cpu==1.14.3` 可读取既有正式索引，本里程碑无需升级向量依赖。

### 缺失输入

- 没有阻止计划启动的关键输入；
- 编码前仍需按仓库规则，用 Firecrawl、Exa 或 Tavily 核对本次实际涉及的 Python 3.14 官方文档契约，并记录链接、结论和适用代码；
- 正式提交前必须重新核对两份源文件 SHA-256、正式索引基线和增量 manifest 基线，不能沿用计划编写时的易变数值。

### 允许的默认值

- S2 对证据不足的标题选择、条号连续性或前置材料归属返回 `review_required`，不得猜测；
- 对来源摘要变化、块顺序非法或提取失败返回 `failed/rejected`，不得进入质量资格；
- CLI 新增通用双轴筛选参数，但不传参数时继续默认筛选 `W + S1`，保持现有命令兼容；
- 联合发布机关以有序列表表达；如现有下游暂时只能接受字符串，则使用稳定分隔形式并保留结构化证据，禁止丢失机关数量和顺序；
- 规则语义发生变化时质量规则集由 `legal-quality-v1` 升为 `legal-quality-v2`，旧报告仍可读取但不得伪装成新规则结果。

## 4. 依赖与包管理工具

| 环境 | 包管理工具 | 本里程碑处理 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；仅在获批后使用 conda 或 `conda run -n fire python -m pip` | 无需新增依赖，沿用现有环境；禁止自行安装 |
| 前端 | 不涉及；不运行 npm、pnpm 或 yarn | 无前端改动，无需安装依赖 |
| 系统工具 | macOS 自带 `textutil`，由现有 W 提取策略调用 | 只读复用，不安装、不替换 |
| 数据与索引 | 现有摄取 CLI、关键词索引和 `faiss-cpu==1.14.3` | 不改索引格式，不新增模型依赖 |

执行中若发现必须新增依赖，应立即停止，列出依赖名称、用途、版本范围、安装位置和包管理工具，待用户确认后再修改计划和继续实施。

## 5. 分卷导航

| 分卷 | Task | 负责内容 | 不负责内容 |
| --- | --- | --- | --- |
| [分卷一](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation-part-1.md) | Task 1—3 | 冻结 W-S2 视图、核验官方契约、扩展元数据证据模型、TDD 实现 S2 边界 | CLI、正式写入 |
| [分卷二](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation-part-2.md) | Task 4—6 | 独立注册 S2、贯通结构化与 chunk 元数据、增加 S2 质量门禁 | 正式数据提交 |
| [分卷三](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation-part-3.md) | Task 7—10 | 通用化批次筛选、两份真实文件验收、临时提交回归、正式导入和文档收口 | S3、PDF/OCR |

## 6. 执行顺序

1. 严格按分卷一 → 分卷二 → 分卷三执行；
2. 每个 Task 先写失败测试，再做最小实现，再跑相关回归；
3. 每个 Phase 开始前重新列出已确认、缺失和采用的默认值；
4. 分卷一只允许只读真实探测；分卷二仍不得写正式 `data/`；
5. 分卷三先做 `--verify-source-only`、`--dry-run` 和临时目录提交，全部通过后才能正式导入；
6. 正式导入后必须核对语料文件、关键词索引、FAISS 向量数、manifest、质量报告和真实检索，不能只看 `committed=2`。

## 7. 全局硬门禁

1. W-S2 只能由唯一 14 文件 fixture 动态筛选，禁止创建第二份同义清单；
2. 运行时只能注册独立 `ContentClass.S2`，禁止出现 `W-S2` 策略键；
3. 前置发布材料必须保存为排除范围，且与正文来源范围零重叠；
4. 所有进入结构化产物的 S2 元数据必须携带来源证据；
5. 前置材料中的条号不能参与目标法规条号计数；
6. 同名标题重复时，只有“标题后紧邻完整连续条文”证据充分才可自动确认；
7. “附件”出现在目标标题之前时不得触发尾部截断；
8. 目标正文必须分别精确包含 32 条和 37 条，条号连续、唯一、非空；
9. 非 `confirmed` 边界不得产生 normalized、structured、chunks 或资格；
10. 真实测试不得使用 `skip`、`xfail` 或文件缺失时提前返回；
11. 所有测试提交使用临时目录，不写正式 `data/`；
12. 正式导入前后必须验证 W-S1 既有 8 份文档仍可检索且数量不减少；
13. 单份失败不回滚已成功文件，但必须保留独立报告并阻止失败文件写入；
14. 禁止更改既有 FAISS 索引维度、模型标识和 Append-Only 发布顺序。

## 8. Git 策略

- 本计划授权实施阶段在每个完整 Phase 通过单元测试、相关回归和真实上游验证后执行一次 `git add` 与 `git commit`；
- commit 说明必须使用中文，只包含该 Phase 已验证的改动；
- 推荐提交说明依次为：`实现S2复合发布边界`、`贯通S2元数据与质量门禁`、`完成W-S2真实摄取验收`；
- 工作区存在非代理产生的改动时必须避开；无法安全避开则停止提交并报告；
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写；
- 当前计划编写任务不执行 commit。

## 9. 里程碑完成定义

只有同时满足以下条件，才能把 S2 和 W-S2 标记为 `implemented`：

- S2 策略独立注册，S1 行为与 S3/S4 安全状态不变；
- 两份 W-S2 均形成 `confirmed` 中间格式；
- 正文分别为第 1—32 条和第 1—37 条，前置材料零污染；
- 版本依据、发布机关和日期均可追溯到来源位置；
- 新增 S2 门禁、现有通用门禁和资格绑定全部通过；
- 两份真实文件的 dry-run 为 `auto_passed=2`，无失败、无人工复核；
- 临时 Append-Only 提交、失败隔离、关键词检索和向量检索通过；
- 正式导入后两份文件均有语料、索引、manifest 和质量报告；
- W-S1 真实回归与仓库完整测试通过；
- 能力路线图、README、文档索引和读取规则与实际状态一致。

计划完成、单元测试通过或 dry-run 通过，都不能单独视为里程碑完成。

## 10. 总体验收命令

**命令执行意图：** 汇总运行 S2 单元测试、W-S2 真实验收和 W-S1 回归。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_ws2_batch.py tests/integration/pipeline/test_ws2_ingestion_real.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py tests/integration/pipeline/test_ws2_qualified_incremental_import.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** 全部 PASS；W-S2 和 W-S1 真实测试均无 skipped/xfailed。

**命令执行意图：** 最终运行仓库完整回归，发现计划范围外的兼容性破坏。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部测试 PASS；若数量较计划编写时增加，以当次测试收集结果为准，但不得少收集既有测试。
