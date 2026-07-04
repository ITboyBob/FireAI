# 法规摄取能力路线图

## 何时必须更新本文

本文是法规摄取工作的总体规划层入口。发生以下任一变化时，负责该变化的设计、计划或实施任务必须在同一任务中同步更新本文，不得把路线图维护留给后续任务：

1. 总体架构、专项设计或 ADR 的决策发生新增、替换、废弃或适用范围变化；
2. 统一入口、编排器、提取策略、正文边界策略、质量资格、提交或批次能力的状态发生变化；
3. 里程碑被创建、拆分、合并、调整范围、开始实施、完成、暂停或取消；
4. 外部依赖、技术选型或人工审批由未决变为获批、被拒，或新增、解除阻塞；
5. 单元测试、集成测试或真实文件验收改变了已有能力结论；
6. 代码现状与本文的能力矩阵、依赖关系或里程碑状态不再一致。

仅修改措辞且不影响上述事实时，无需更新能力状态。更新本文时必须同时给出代码、测试、真实验收或已批准文档中的证据；不得仅凭计划完成度把能力标记为已实现。

## 1. 文档职责

本文回答三个问题：

- 当前法规摄取系统已经具备哪些能力；
- 下一阶段建设什么，以及各能力之间有什么依赖；
- 每项能力由哪个里程碑实施和验收。

本文不定义组件接口、算法和质量规则，也不列出逐文件编码步骤。架构规则由总体架构、专项设计和 ADR 负责；可执行步骤由各里程碑实施计划负责。

## 2. 三层文档结构

| 层级 | 负责内容 | 不负责内容 |
| --- | --- | --- |
| 架构设计层 | 总体架构、组件边界、稳定接口、专项规则和关键 ADR | 具体 Task、测试命令和当前进度 |
| 总体规划层 | 本文维护能力矩阵、依赖、里程碑顺序和当前状态 | 提前设计尚未进入里程碑的策略算法 |
| 里程碑执行层 | 针对当前新增能力编写 Task、TDD 步骤、真实验收和提交策略 | 重复定义全局架构或复制其他里程碑计划 |

计划扩展遵循“按新增能力写计划、按策略组合做真实验收”：

- 新增 PT-S1 时，只为 PT 提取能力及 PT-S1 组合验收编写计划，复用已有 S1、质量资格和提交能力；
- 新增 W-S2 时，只为 S2 边界能力及 W-S2 组合验收编写计划，复用已有 W；
- 不为 W-S1、W-S2、PT-S1、PT-S2 等每个组合复制一套完整入口和实施计划。

## 3. 状态定义

能力和里程碑只使用以下状态：

| 状态 | 含义 |
| --- | --- |
| `planned` | 范围和依赖已登记，但尚无足以证明能力可用的完成证据 |
| `in_progress` | 已进入实施，仍有 Task、门禁或真实验收未完成 |
| `implemented` | 代码、相关测试和所需真实验收均已完成，并有可追溯证据 |
| `blocked` | 关键审批、依赖、样本或技术结论缺失，当前不能安全继续 |

“设计已批准”或“计划已写完”不等于 `implemented`。同一组件存在旧能力和目标能力时，矩阵必须明确区分，避免把旧脚本可运行误写成新架构已经完成。

## 4. 当前能力矩阵

当前建设基线是：统一安全入口、上游策略路由、W 提取策略、S1 正文边界、法规语义质量资格和 Append-Only 提交已经完成实现与真实验收。W-S1 是第一个已完成的端到端里程碑；后续里程碑继续补充 PT、PS、S2、S3 等尚未实现的策略能力。

| 能力 | 当前状态 | 当前结论 | 目标或完成证据 | 所属里程碑 |
| --- | --- | --- | --- | --- |
| 唯一统一 CLI | `implemented` | `scripts/import_new_corpus.py` 收敛为唯一薄入口；保留位置参数/`--source` 单文件语法，新增 `--batch-manifest` 显式批次、`--dry-run` 和 `--verify-source-only`；参数互斥、退出码和报告路径输出均有测试覆盖 | 保留兼容调用方式，所有输入统一委托编排器；未支持类型零写入 | W-S1 |
| 统一摄取编排器 | `implemented` | 已完成 `run_legal_ingestion()` 单文件/批次统一入口、逐文件处理、失败隔离、`--dry-run` 只生成报告不提交；`prepare()` 仍只读 | 固定“分类→提取→边界→质量资格→提交”顺序，禁止旁路 | W-S1 |
| W：Word 提取策略 | `implemented` | 真实签名、MIME、只读转换证据、双轴候选分类、内存 Word 提取和 Word 专属门禁已实现；评估基线 8 份 W-S1 文件全部通过 `source_identity`、`body_purity`、`exclusion_isolation` 等 Word 相关质量门禁 | `tests/integration/pipeline/test_ws1_legal_corpus_quality.py` 对 8 份真实文件逐文件断言门禁通过；`scripts/import_new_corpus.py --batch-manifest ... --dry-run` 输出 `auto_passed=8` | W-S1 |
| PT：文本型 PDF 提取策略 | `planned` | 已有分类设计，尚未进入实现里程碑 | 后续计划只补 PT 提取与相关组合验收，不预写算法 | 后续里程碑待创建 |
| PS：扫描型 PDF 提取策略 | `blocked` | OCR 引擎、中文资源和图像预处理依赖尚未获批 | 完成官方文档调研、依赖审批、真实样本探针后才能进入实施 | 后续里程碑待创建 |
| S1：纯正文边界策略 | `implemented` | 已实现唯一标题、连续条号、尾部排除、confirmed 中间格式和 paragraph 子单元拼接的跨层一致性校验；评估基线 8 份 W-S1 文件全部 `boundary.status=confirmed`，条号连续唯一、条文非空、无页眉页脚和印发尾注污染 | `tests/integration/pipeline/test_ws1_legal_corpus_quality.py` 逐文件断言 `boundary_confirmed`、`article_start`、`article_numbers`、`article_non_empty`、`body_purity`、`cross_layer_consistency`、`chunk_coverage` 均通过 | W-S1 |
| S2：复合发布边界策略 | `implemented` | 已实现 `LegalDocumentIntermediate` 复合发布边界、`leading_publication_material` 排除范围、发布机关/日期/版本依据等元数据证据与跨层一致性校验；2 份 W-S2 真实文件质量门禁全部 `pass` 并正式提交 | `tests/integration/pipeline/test_ws2_formal_index_state.py` 对真实 data/ 目录断言两份 W-S2 文件 manifest、语料、关键词索引、向量映射和结构条数一致；`tests/integration/pipeline/test_ws2_qualified_incremental_import.py` 覆盖隔离失败与回滚 | W-S2 |
| S3：正文后排除策略 | `implemented` | 已实现独立 `ContentClass.S3` 正文后排除策略，确认唯一标题 + 连续条号后，识别并排除印发信息、附件目录、文书模板、评分表和页码域等尾部信号；29 条正文通过 v3 质量门禁并正式提交 | `tests/integration/pipeline/test_ws3_formal_index_state.py` 在真实 `data/` 目录断言 W-S3 文件 manifest、语料、关键词索引、向量映射一致，正文 29 条、干净 chunk 34 条，v3 PASS；`tests/integration/pipeline/test_ws3_qualified_incremental_import.py` 覆盖临时目录提交与失败隔离 | W-S3 |
| S4：混合不确定处理 | `planned` | 已确定不得自动提交，具体人工复核流程未实施 | 稳定输出 `review_required`，任何自动提交路径均被测试阻断 | 后续里程碑待创建 |
| 通用质量资格 | `implemented` | `CommitQualification` 绑定源摘要、质量报告和三类 staged 产物摘要；`commit_qualified_staged_import()` 在第一次 preflight 前校验绑定，失败零写入 | 资格绑定源摘要、质量报告和 staged 产物摘要，失败时零提交 | W-S1 |
| Append-Only 单文件提交 | `implemented` | staging、两次 preflight、索引追加、回滚和 manifest 已有实现 | W-S1 只复用并回归验证，不重写提交事务 | 既有增量导入 |
| 批次发现与逐文件隔离 | `implemented` | `_run_batch_legal_ingestion()` 实现逐文件评估、串行提交、独立质量报告和批次汇总；失败文件不阻断其他文件，也不回滚已提交文件 | 批次只负责发现、调度和汇总；每份文件独立提交，失败互不污染 | W-S1 |
| 14 文件真实验收 | `in_progress` | 唯一 fixture 已与真实 14 文件核对；11 份 Word 已完成只读真实分类；W-S1 8 份、W-S2 2 份、W-S3 1 份已全部通过质量门禁并正式提交，正式索引共 20 份文档、876 个关键词 chunk、876 个 FAISS 向量，manifest 共 14 条记录；3 份 PDF 待 PT/PS 策略覆盖 | 继续按当前计划实现 PT、PS 策略并完成对应真实文件验收；最终 14 份均有处理状态和可追溯证据 | 跨里程碑收口 |

## 5. 当前里程碑

### 5.1 W-S1 端到端摄取

**状态：** `implemented`

本里程碑负责：

- 把旧增量导入脚本收敛为唯一薄 CLI；
- 建立统一编排器、策略注册和稳定结果语义；
- 实现 W 提取策略和 S1 正文边界策略；
- 建立通用质量资格并接入现有 Append-Only 提交；
- 用评估基线中的 8 份 W-S1 真实文件完成组合验收。

本里程碑不实现 PT、PS、S2、S3 的处理算法，也不让 S4 自动提交。其他策略当前只登记能力状态、稳定接口和安全处置结果：未实现能力返回 `unsupported`，证据不充分返回 `review_required`，明确执行错误返回 `failed`。

W-S1 完成不等于 14 文件全量摄取完成，也不等于多格式法规摄取全部实现。

### 5.2 S2 边界能力与 W-S2 组合验收

**状态：** `implemented`

本里程碑负责：

- 复用已实现的 W 提取、统一编排、质量资格和 Append-Only 提交能力；
- 实现独立 `ContentClass.S2` 复合发布边界策略；
- 隔离目标法规之前的政府令、修改决定、签署机关和日期等材料；
- 让版本依据、发布机关和日期等元数据带来源位置并跨层一致；
- 把批次清单的双轴筛选从硬编码 W-S1 改为通用参数，同时保持旧命令兼容；
- 用 `河北省消防设施管理规定.docx` 和 `社会消防安全教育培训规定.doc` 完成 W-S2 真实组合验收。

本里程碑不实现 S3、PT、PS/OCR、人工复核工作台，也不新增 W-S2 组合策略或第二个 CLI。完成证据：

- `tests/integration/pipeline/test_ws2_formal_index_state.py` 在真实 `data/` 目录下断言两份 W-S2 文件的 manifest 记录、结构化条数、chunk 数、关键词索引和向量映射一致；
- `tests/integration/pipeline/test_ws2_qualified_incremental_import.py` 覆盖 digest 失败隔离与 manifest 写入失败回滚；
- 完整回归 `pytest -q` 376 项通过。

### 5.3 S3 边界能力与 W-S3 组合验收

**状态：** `implemented`

本里程碑已经在 Linear“消防AI”项目中创建为“W-S3 尾部排除内容”，当前已完成全部 Task 并正式导入真实 `data/`。

本里程碑负责：

- 复用已实现的 W 提取、统一编排、质量资格和 Append-Only 提交能力；
- 实现独立 `ContentClass.S3` 正文后排除策略；
- 在确认完整法规正文后，排除印发信息、附件目录、文书模板、评分表和页码域；
- 增加 S3 专属尾部存在、位置、覆盖和输出纯净门禁；
- 用 `河北省消防救援机构执法过错责任追究规定.doc` 完成 29 条正文的 W-S3 真实组合验收。

完成证据：

- 正式批次 `c132d0f3-aa52-40cc-a1c8-7e26cb0209e1`：`selected=1`、`committed=1`、`failed=0`，`河北省消防救援机构执法过错责任追究规定.doc` 成功提交；
- 结构化文件包含 29 条正文，`content_class=S3`、`boundary_status=confirmed`，尾部文书模板、印发信息、页码域未进入正文；
- 切块文件 34 条干净 chunk，全部绑定同一 `document_id`，尾部污染物未进入 chunk；
- v3 质量门禁 `s3_tail_exclusion_presence`、`s3_tail_position`、`s3_tail_coverage`、`s3_output_purity` 全部 PASS；
- `tests/integration/pipeline/test_ws3_formal_index_state.py` 在真实 `data/` 下断言 manifest、关键词索引、向量映射增量正确，W-S1/W-S2 历史文件仍可检索；
- `tests/integration/pipeline/test_ws3_qualified_incremental_import.py` 覆盖临时目录 Append-Only 提交、失败隔离与单文件 `force_batch` 批次路径回归；
- 完整回归 `pytest -q` 471 项通过。

本里程碑不实现 PS-S3、PDF/OCR、S4 人工复核工作台、组合策略或第二个 CLI。当前设计入口为 [S3 正文后排除边界专项设计](../architecture_or_strategy/2026-07-04-s3-trailing-exclusion-boundary-design.md)，执行入口为 [S3 边界能力与 W-S3 组合验收计划](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation.md)。

## 6. 后续里程碑安排原则

后续里程碑在创建前必须先检查：

1. 所需上游能力是否已经 `implemented`；
2. 真实样本和验收基线是否足够；
3. 是否需要新增依赖，以及依赖是否已按仓库规则获批；
4. 新增的是提取策略、边界策略、通用能力还是组合验收；
5. 是否可以复用既有策略，避免重复入口、编排器、质量资格或提交事务。

建议的演进顺序不是固定承诺，应随证据更新：

1. 以已完成的 W-S1 统一入口和公共主干为复用基线；
2. 按已创建的 W-S2 计划实现 S2，并完成 2 份 W-S2 组合验收；
3. 在 W 和已有 S 类策略稳定后实现 S3，并完成对应 W 组合验收；
4. 完成 PT 真实探针和提取策略，再复用已实现的 S 类策略；
5. PS 仅在 OCR 依赖获批并完成真实样本探针后进入实施；
6. 最后汇总 14 文件状态，完成跨策略全量验收。

## 7. 状态变更记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-06-29 | 创建路线图；W-S1 登记为首个端到端里程碑；仅 W、S1 和公共主干进入当前范围 | 已批准的三层文档结构与统一入口架构决策 |
| 2026-06-29 | W-S1 开始实施；完成14文件基线冻结、来源模型、批次清单、11份真实 Word 探测与双轴分类 | 提交 `f22e6d3`、`b99ab63`、`9c51395` 及对应无 skip 测试 |
| 2026-06-29 | 完成双轴注册与只读编排接缝、Word 内存候选提取、S1 边界和统一中间格式；能力保持 `in_progress` | 提交 `b6821ab`、`b02fb91`；Task 6 单元30项和4份真实样本验证 |
| 2026-06-29 | W-S1 质量验收完成：`cross_layer_consistency` 修复 paragraph 子单元拼接，8 份真实 W-S1 文件 dry-run 全部门禁通过；W 提取策略与 S1 边界策略状态更新为 `implemented`；`test_incremental_import_real_smoke.py` 改为缺失即失败并修正真实文件路径 | `tests/unit/services/test_legal_quality_gates.py::test_cross_layer_article_with_paragraph_children_passes`、`tests/integration/pipeline/test_ws1_legal_corpus_quality.py`、批次 CLI dry-run `auto_passed=8` |
| 2026-06-30 | W-S1 8 份真实文件完成正式 Append-Only 提交；里程碑更新为 `implemented`。正式语料、关键词索引、向量索引与 manifest 均包含全部 8 份文件，质量报告全部为 `pass` | 批次 `8474b7ab-265a-41ce-8b7d-5fd64f9aecba`：`selected=8`、`committed=8`、`failed=0`；正式索引共 17 份文档、771 个关键词 chunk、771 个 FAISS 向量，增量 manifest 共 11 条记录 |
| 2026-06-30 | `faiss-cpu` 从 1.13.2 升级到 1.14.3，依赖下限同步提高；Python 3.14 下的 3 条 SWIG `DeprecationWarning` 消失，既有 W-S1 正式索引无需重建 | 严格警告模式下 FAISS/检索单元测试 12 项、W-S1 真实回归 27 项通过；仓库完整回归 312 项通过；正式 `faiss.index` 仍为 384 维、771 个向量，并可命中 `消防监督检查规定` 第十条 |
| 2026-06-30 | 创建 S2 边界能力与 W-S2 组合验收里程碑及三分卷执行计划；S2 保持 `planned`，未开始代码实现 | 两份 W-S2 真实 Word 只读探测确认 32/37 条目标正文及“修改决定在前”“联合发布信息在前”两类结构；计划明确复用 W 和公共主干、先 TDD 后真实提交 |
| 2026-06-30 | S2 边界策略与 W-S2 组合验收完成：`leading_publication_material` 隔离、元数据证据与跨层一致性校验落地；2 份 W-S2 真实文件正式提交；S2 与 W-S2 里程碑状态更新为 `implemented`；manifest 兼容旧记录并完成 `source_sha256` 迁移 | 单次导入 `doc_0e84d13a099b`（33 chunks）与 `doc_aa2b9b6c20ab`（38 chunks）；`tests/integration/pipeline/test_ws2_formal_index_state.py` 通过；完整回归 376 项通过；正式索引共 19 份文档、842 关键词 chunks、842 FAISS 向量，manifest 13 条记录 |
| 2026-07-04 | 批准 S3 正文后排除专项设计并登记 W-S3 里程碑；S3 保持 `planned`，尚未编写实施计划或业务代码 | 唯一 W-S3 真实文件只读探针确认 29 条正文，正文后存在印发信息、附件目录、5 套文书模板和页码域；专项设计明确多信号边界、零写入和真实验收规则 |
| 2026-07-04 | 完成 W-S3“总览 + 2 分卷”实施计划；S3 仍为 `planned`，未开始业务代码或正式导入 | 计划拆为 8 个 Task，固定官方契约核验、TDD、v3 门禁、真实预演、临时回滚、正式导入和逐 Task 中文 commit 策略 |
| 2026-07-04 | S3 边界策略与 W-S3 组合验收完成：独立正文后排除策略落地，29 条正文真实文件正式提交；S3 与 W-S3 里程碑状态更新为 `implemented`；单文件批次导入新增 `force_batch` 参数以修复 CLI 单来源批次路径 | 正式批次 `c132d0f3-aa52-40cc-a1c8-7e26cb0209e1`：`selected=1`、`committed=1`、`failed=0`；`tests/integration/pipeline/test_ws3_formal_index_state.py` 与 `test_ws3_qualified_incremental_import.py` 通过；完整回归 471 项通过；正式索引共 20 份文档、876 关键词 chunks、876 FAISS 向量，manifest 14 条记录 |
