# S3 边界能力与 W-S3 组合验收实施计划（分卷一）

> 本卷执行 Task 1—5：先冻结事实和官方契约，再以 TDD 实现、注册 S3，并建立 v3 质量门禁。不得修改正式 `data/`。

**目标：** 从唯一 14 文件基线派生 1 项 W-S3 视图，在不改变 S1/S2 行为的前提下实现独立 S3 边界策略，使真实文件形成仅含第一条至第二十九条的 confirmed 中间格式并通过 S3 专属门禁。

**架构：** 先把 S1/S2 已共同依赖的标题、条号和正文单元纯函数收敛到公共模块，再由 `S3BoundaryStrategy` 按“正文锚点 → 尾部强信号 → 辅助信号 → 全尾部覆盖”顺序独立判定。注册表和编排器只按 `ContentClass.S3` 接线；质量门禁交叉检查提取块、中间格式、结构化条文和 chunks。

**技术栈：** Python 3.14 标准库、现有领域模型、pytest；全部命令通过 `conda run -n fire` 执行。
---

## 1. 权威输入与本卷边界

- [总计划](./2026-07-04-s3-boundary-and-w-s3-acceptance-implementation.md)
- [S3 专项设计](../architecture_or_strategy/2026-07-04-s3-trailing-exclusion-boundary-design.md)
- [能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)
- [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [todo 法规语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)

本卷允许修改边界公共函数、S3 策略、注册表、编排器、结构/切块适配、质量门禁及对应测试。不得运行正式导入命令，不得修改正式语料、索引或 manifest。

## Phase 1：事实、策略与质量能力

### 已确认

- 唯一 fixture 为 `tests/fixtures/legal_ingestion/todo_baseline.json`，W-S3 应恰好 1 项；
- 真实文件正文为第一条至第二十九条；
- 印发信息位于“附件”标题之前，尾部随后包含附件目录、5 套文书模板和页码域；
- 正文第二十至二十二条合法引用文书名称，不能按关键词截断；
- S1/S2 已实现并共享 `legal_content_boundary.py` 中的私有纯函数；
- 当前注册表和默认编排只实现 S1/S2，S3 稳定返回 `unsupported`；
- 当前质量规则集为 `legal-quality-v2`，没有 S3 专属 gate。

### 缺失

- Task 1 尚需核对最新官方运行时契约；
- S3 公共函数重构前尚无独立公共模块；
- 干净 chunk 数留到分卷二 Task 6 冻结，不在本卷猜测；
- 若真实尾部含设计未覆盖的非空块，本卷必须停止并回到设计。

### 默认值

- 不新增依赖；
- 公共函数重构必须无行为变化，先保护 S1/S2 再移动；
- S3 证据不足返回 `review_required`，机械契约损坏返回 `failed/rejected`；
- 结构解析与切块继续复用现有通用入口，只补充必要的 S3 一致性断言；
- 所有测试使用临时目录或只读真实源。

### 依赖与包管理工具

- 后端：conda 环境 `fire`，本 Phase 无需新增依赖；
- 前端：不涉及，不使用 npm、pnpm 或 yarn；
- 系统工具：只读复用 `/usr/bin/textutil`；
- 联网核验：只能通过 Firecrawl、Exa 或 Tavily 读取官方文档；
- Git：每个 Task 完成并验证后，按总计划执行一次中文 commit；不 push。

### Task 1：冻结 W-S3 派生视图并核验运行时契约

**阶段输入检查：** 已确认唯一基线、真实路径、预期 `W + S3` 和 29 条正文；缺失官方契约核验记录；无需新增依赖，沿用 conda 环境 `fire`。

**文件：**

- 新增：`tests/integration/pipeline/test_todo_ws3_scope.py`
- 新增：`docs/reference_material/2026-07-04-s3-runtime-contract-verification.md`
- 修改：`docs/system_meta/文档索引.md`

**步骤 1：先写失败范围测试。**

测试只用 `expected_extraction_class == "W"` 且 `expected_content_class == "S3"` 从唯一 fixture 过滤，断言：

- 恰好 1 项，路径为总计划指定文件；
- `expected_article_count == 29`；
- 风险码包含 `tail_template` 和 `word_page_field`；
- 真实文件存在，且只读探测前后 SHA-256 不变；
- 当前真实分类仍为 `W + S3`；
- 仓库中不存在第二份 `ws3_baseline.json` 或生产级 `Ws3` 组合清单。

**命令执行意图：** 证明测试能够发现 W-S3 派生视图、真实路径或分类契约缺失。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws3_scope.py -q
```

**预期输出：** 首次因测试文件尚未实现而 FAIL；不得用 skip 代替。

**步骤 2：查询并记录最新官方契约。**

通过 Firecrawl、Exa 或 Tavily 读取官方文档，仅记录实际涉及的结论：

- Python 3.14 `re.Pattern.fullmatch()`、`finditer()`、命名捕获组和 Unicode 行为；
- frozen/slots dataclass 与 tuple 默认值行为；
- `Enum` 非法值异常语义；
- pytest 参数化、临时目录和失败断言的当前用法。

核验文档必须包含：官方链接、访问日期、与计划假设的对应关系、最小实验、实验输出和影响的代码位置。若官方结论与设计冲突，停止执行并先修订设计和计划。

**步骤 3：实现最小测试视图并运行真实分类。**

筛选逻辑只存在于测试或现有通用 manifest 选择入口，不新增生产级 W-S3 helper。真实分类调用现有 `classify_source()`，不得在测试中重写分类算法。

**命令执行意图：** 验证唯一基线、真实文件和当前分类对 1 项 W-S3 的结论一致。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws3_scope.py tests/integration/pipeline/test_legal_source_classifier_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；源摘要不变。

**Checkpoint：** 当前只证明“该文件应由 W 提取和 S3 处理”，不表示边界确认或可以提交。验证完成后按总计划提交：`冻结W-S3范围并核验运行时契约`。

### Task 2：抽取边界公共纯函数且保持 S1/S2 行为不变

**阶段输入检查：** Task 1 已通过，S1/S2 真实回归可运行；缺失独立公共函数模块；无需新增依赖。

**文件：**

- 新增：`app/services/legal_boundary_common.py`
- 新增：`tests/unit/services/test_legal_boundary_common.py`
- 修改：`app/services/legal_content_boundary.py`
- 修改：`app/services/legal_s2_boundary.py`
- 修改：`tests/unit/services/test_legal_content_boundary.py`
- 修改：`tests/unit/services/test_legal_s2_boundary.py`

**步骤 1：先写公共 API 失败测试。**

公共模块只暴露 S1/S2/S3 都需要的 `ARTICLE_PATTERN`、`HEADING_PATTERN`、`normalize_title()`、`article_number()`、`chinese_number_to_int()`、`build_body_units()` 和最小来源范围纯函数。

测试固定标题空白/标点规范化、中文与阿拉伯条号、编章节识别、article/paragraph 父子关系、来源范围单调性。不得把 S1 尾页、S2 元数据或 S3 尾部规则放进公共模块。

**命令执行意图：** 证明公共模块尚不存在，并固定迁移后的最小 API。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_boundary_common.py -q
```

**预期输出：** 因模块或公开函数不存在而 FAIL。

**步骤 2：移动最小纯函数并改造调用方。**

- 从 `legal_content_boundary.py` 移动公共实现，不复制；
- S1、S2 改用公共模块；
- 需要兼容旧测试导入时仅保留短期显式再导出，不保留两份实现；
- S1 的尾页识别和 S2 的候选/元数据逻辑仍留在各自模块；
- 不修改任何规则版本、原因码或真实输出。

**步骤 3：运行公共函数和 S1/S2 单元回归。**

**命令执行意图：** 证明重构只改变代码位置，不改变边界结果。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_boundary_common.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_s2_boundary.py -q
```

**预期输出：** 全部 PASS；既有原因码和来源范围不变。

**步骤 4：运行真实 S1/S2 回归。**

**命令执行意图：** 用 10 份已验收 Word 文件证明公共函数迁移无行为变化。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws2_ingestion_real.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；条数、边界和质量结论不变。

**Checkpoint：** 公共模块只提供纯函数，尚未实现 S3。验证完成后按总计划提交：`重构法规边界公共辅助函数`。

### Task 3：TDD 实现独立 S3 正文后排除策略

**阶段输入检查：** Task 2 公共函数稳定且真实 W-S3 只有 1 项；缺失 `S3BoundaryStrategy` 与真实边界测试；无需新增依赖。

**文件：**

- 新增：`app/services/legal_s3_boundary.py`
- 新增：`tests/unit/services/test_legal_s3_boundary.py`
- 新增：`tests/integration/pipeline/test_ws3_ingestion_real.py`
- 必要时修改：`app/services/legal_boundary_common.py`
- 必要时修改：`tests/unit/services/test_legal_boundary_common.py`

**步骤 1：先写 S3 失败矩阵。**

单元测试至少覆盖：

- 唯一标题、连续条文、印发信息、附件目录和连续模板形成 confirmed S3；
- 印发信息位于附件标题之前时，首个排除范围从印发信息开始；
- 正文中引用“审批表”“决定书”但未进入尾部时不得截断；
- “附件”出现在目标标题之前时不得截断；
- 没有附件标题但有连续模板标题与字段序列时形成 S3 候选；
- 只有页码/普通印发尾注、没有实质强信号时返回 `review_required:s3_tail_signal_missing`；
- 最后一条后存在未知非空块时返回 `review_required:s3_unclassified_tail_block`；
- 尾部起点后再次出现正式条文时返回 `review_required:s3_article_after_tail_start`；
- 多个同等尾部起点、条号断裂、块顺序非法、源摘要变化分别安全阻断；
- blocked/review 结果正文为空；
- 排除范围按位置递增、互不重叠且全部晚于正文。

**命令执行意图：** 证明 S3 模块尚未实现且现有 S1 不能安全处理该矩阵。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_s3_boundary.py -q
```

**预期输出：** 因模块或策略不存在而 FAIL。

**步骤 2：实现正文锚点和尾部信号。**

`S3BoundaryStrategy(kind="S3")` 严格按以下顺序：

1. 校验提取状态、来源摘要和块顺序；
2. 唯一匹配目标标题；
3. 找到第一条并验证连续条号；
4. 确定最后一条及其 paragraph 子单元；
5. 在正文之后寻找附件、连续模板、评分表或模板字段序列强信号；
6. 向前吸收与强信号连续的印发信息和允许噪声；
7. 向后将非空块分类为设计允许的尾部类型；
8. 检查未知块、正文重入、范围重叠和多个候选；
9. 唯一时构造 confirmed 中间格式，否则构造空正文的 review/rejected 结果。

排除 `kind` 只能来自设计规定的稳定集合，不得把排除正文写入 diagnostics、reason 或 report。

**步骤 3：用真实文件固定 29 条正文。**

真实集成测试从唯一 fixture 派生文件，调用现有 W 提取器和 S3 策略，断言：

- `boundary.status == "confirmed"`；
- parsed 前的 `body_units` 恰好覆盖第一条至第二十九条；
- 第二十九条以正式废止条款结束；
- 首个排除范围覆盖附件前的印发信息；
- 后续范围覆盖附件目录、5 套模板和页码域；
- body_text、diagnostics 和 report 不复制排除正文；
- 源文件读取前后 SHA-256 不变。

**命令执行意图：** 用真实上游文件验证多信号边界，而不是只验证人工构造文本。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_s3_boundary.py tests/integration/pipeline/test_ws3_ingestion_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；真实边界 confirmed，正文为 29 条。

**步骤 4：回归 S1/S2。**

**命令执行意图：** 证明新增 S3 没有放宽 S1 或改变 S2。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_s2_boundary.py tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws2_ingestion_real.py -q
```

**预期输出：** 全部 PASS；S1/S2 条数和边界保持不变。

**Checkpoint：** S3 可独立生成中间格式，但尚未注册或取得质量资格。验证完成后按总计划提交：`实现S3正文后排除边界`。

### Task 4：独立注册 S3 并贯通编排、结构和切块

**阶段输入检查：** Task 3 能产生 confirmed S3 中间格式；缺失默认注册与端到端只读编排；无需新增依赖。

**文件：**

- 修改：`app/services/legal_strategy_registry.py`
- 修改：`app/services/legal_ingestion_orchestrator.py`
- 修改：`tests/unit/services/test_legal_strategy_registry.py`
- 修改：`tests/unit/services/test_legal_ingestion_orchestrator.py`
- 修改：`tests/unit/services/test_structure_parser.py`
- 修改：`tests/unit/services/test_chunk_builder.py`
- 修改：`tests/integration/pipeline/test_ws3_ingestion_real.py`

**步骤 1：先写失败路由测试。**

测试固定：

- `build_boundary_strategy_registry(..., s3_strategy=...)` 独立注册 S3；
- S1、S2、S3 为 implemented，S4 仍为 review_required；
- kind 错误、重复注册、`"W-S3"` 或 tuple 组合键均失败；
- 默认 `run_legal_ingestion()` 对 W-S3 选择 W 提取器和 S3 策略；
- S3 review/failed 时不调用结构解析、质量资格或提交；
- W-S1/W-S2 仍选择各自策略。

**命令执行意图：** 证明默认编排尚未注册 S3。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 新 S3 断言先 FAIL；既有 S1/S2 断言仍 PASS。

**步骤 2：做最小注册与默认接线。**

- 给 registry builder 增加可选 `s3_strategy`；
- 默认编排器实例化 `S3BoundaryStrategy`；
- 保持分类 → W 提取 → S3 边界 → 解析 → 切块 → 质量的既有顺序；
- 不新增 `Ws3Strategy`、`Ws3Service`、CLI 分支或提交旁路。

**步骤 3：固定 structured/chunks 的 S3 契约。**

现有 `parse_legal_intermediate()` 和 `build_intermediate_chunks()` 应直接复用，但测试必须证明：

- parsed `content_class == "S3"`、`boundary_status == "confirmed"`；
- 29 条 parsed article 均有正文范围；
- 每个 chunk 的 `content_class`、来源摘要和来源范围与 intermediate 一致；
- chunk 来源范围全部位于正文边界内；
- 任一排除范围文本不得进入 parsed/chunks。

若通用函数已经满足，不修改生产代码；禁止为 S3 创建第二套 parser/chunker。

**命令执行意图：** 验证 S3 从注册表贯通到结构和切块，且无组合适配器。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/integration/pipeline/test_ws3_ingestion_real.py -q
```

**预期输出：** 全部 PASS；真实 W-S3 形成 29 条 structured 正文和边界内 chunks。

**步骤 4：运行 W-S1/W-S2 编排回归。**

**命令执行意图：** 证明默认注册增加 S3 不改变已实现策略。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws2_ingestion_real.py -q
```

**预期输出：** 全部 PASS，无新增非提交状态。

**Checkpoint：** S3 已能只读贯通，但 Task 5 通过前不得签发资格。验证完成后按总计划提交：`接入S3独立策略路由`。

### Task 5：增加 S3 专属门禁并升级质量规则集

**阶段输入检查：** Task 4 可产生 S3 structured/chunks；缺失四项 S3 专属 gate 与 v3 资格绑定；无需新增依赖。

**文件：**

- 修改：`app/services/legal_quality_gates.py`
- 修改：`app/services/legal_ingestion_orchestrator.py`
- 修改：`tests/unit/services/test_legal_quality_gates.py`
- 修改：`tests/unit/services/test_legal_ingestion_orchestrator.py`
- 新增：`tests/integration/pipeline/test_ws3_legal_corpus_quality.py`
- 修改：`tests/integration/pipeline/test_ws1_legal_corpus_quality.py`
- 修改：`tests/integration/pipeline/test_ws2_legal_corpus_quality.py`

**步骤 1：先写失败门禁矩阵。**

新增设计规定的四项 gate：

1. `s3_tail_exclusion_presence`；
2. `s3_tail_position`；
3. `s3_tail_coverage`；
4. `s3_output_purity`。

测试至少覆盖：

- 合法 S3 全部 PASS；
- 缺少实质尾部范围为 FAIL；
- 排除范围早于或重叠正文为 FAIL；
- 排除范围倒序或互相重叠为 FAIL；
- 正文后存在未解释非空块为 REVIEW_REQUIRED；
- 排除块文本进入 body unit、parsed article 或 chunk 为 FAIL；
- gate 的 measured/evidence_refs 不复制排除正文；
- 任一 review/fail 都不能生成 `CommitQualification`；
- S1/S2 不运行 S3 专属 gate，但保留全部既有 gate。

**命令执行意图：** 证明 v2 无法验证 S3 尾部完整覆盖和跨层纯净。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 新 S3 gate 与 v3 断言先 FAIL。

**步骤 2：实现门禁并升级规则集。**

- 将 `RULESET_VERSION` 提升为 `legal-quality-v3`；
- 先运行全部通用 gate，再按 `ContentClass.S2/S3` 追加各自 gate；
- gate 只能核验证据，不重新实现边界算法；
- 运行时可读取 `ExtractionResult.text_blocks` 比对范围，但报告不得保存原文；
- overall 非 pass 时保持零资格、零提交；
- 资格摘要绑定完整 v3 报告。

**步骤 3：运行真实 W-S3 质量矩阵。**

真实测试断言：

- 通用 gate 和四项 S3 gate 全部 PASS；
- overall=pass、ruleset=`legal-quality-v3`；
- article count 为 29；
- 第二十九条、所有 chunks 和报告均无尾部污染；
- 风险码 `tail_template`、`word_page_field` 对应的排除范围存在；
- 无 skip、xfail 或缺失时 return。

**命令执行意图：** 用真实源文件证明 S3 是“完整解释并排除尾部”，而非简单截断。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_ws3_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；真实报告为 v3 overall=pass。

**步骤 4：升级并回归 S1/S2 质量断言。**

只把既有测试的规则版本期望更新为 v3；不得改变 S1/S2 条数、gate 集合或算法结果。

**命令执行意图：** 证明 v3 版本升级没有改变 W-S1/W-S2 的业务结果。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py tests/integration/pipeline/test_ws2_qualified_incremental_import.py -q
```

**预期输出：** 全部 PASS；10 份已验收 Word 文件仍合格。

**Checkpoint：** S3 已获得可测试的 v3 质量资格，但尚未执行真实 CLI 预演或任何提交。验证完成后按总计划提交：`增加S3专属质量门禁`。

## 2. 分卷完成检查

**命令执行意图：** 汇总运行本卷新增能力和 W-S1/W-S2 回归。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_boundary_common.py tests/unit/services/test_legal_s3_boundary.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_todo_ws3_scope.py tests/integration/pipeline/test_ws3_ingestion_real.py tests/integration/pipeline/test_ws3_legal_corpus_quality.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；正式 `data/` 没有变化。

完成证据必须证明：无新增依赖；W-S3 只有一个事实源；S3 独立注册；29 条正文无尾部污染；v3 门禁完整；S1/S2 真实回归稳定。分卷完成后才能进入 Task 6。
