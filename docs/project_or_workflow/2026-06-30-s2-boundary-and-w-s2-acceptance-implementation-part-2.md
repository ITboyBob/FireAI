# S2 边界能力与 W-S2 组合验收实施计划（分卷二）

> 本卷执行 Task 4—6：把 S2 接入独立策略路由，贯通元数据，并建立提交前质量门禁。仍不得写正式 `data/`。

**目标：** 让统一编排器能够按 `ContentClass.S2` 选择新策略，使 S2 元数据从中间格式可靠传到 structured 和 chunks，并用跨层门禁阻止无证据或被前置材料污染的产物取得提交资格。

**架构：** 注册表继续分别按 W/PT/PS 和 S1/S2/S3/S4 路由。中间格式中的 target 元数据是 S2 的权威来源；结构解析器不得在排除前置材料后又从纯正文猜测发布机关和日期。质量门禁使用提取块、中间格式、结构化产物和 chunks 交叉验证。

**技术栈：** Python 3.14、现有编排器、pytest、现有质量资格模型；无需新增依赖。

---

## 1. 权威输入与本卷边界

- [总计划](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation.md)
- [分卷一](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation-part-1.md)
- [法规摄取总体架构](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)
- [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)

本卷允许修改注册表、编排器、结构解析、切块、质量门禁和对应测试；不得修改 CLI 筛选、正式 manifest 或正式索引。

## Phase 2：路由、元数据传播与资格

### 已确认

- 分卷一必须已经通过，S2 策略可独立产生 confirmed 中间格式；
- W 提取策略已经实现，不应复制或建立 W-S2 适配器；
- 当前默认边界注册表只注册 S1，S2 仍返回 unsupported；
- 当前 `parse_legal_intermediate()` 主要从纯正文解析机关和日期，会丢失已经排除的 S2 前置元数据；
- 当前 chunk 未包含 `revision_events` 和 `version_basis`，需要补齐与结构化产物的一致性；
- 当前质量规则集 `legal-quality-v1` 没有 S2 专属证据门禁。

### 缺失

- 若分卷一没有提供稳定 `MetadataEvidence`，本卷不得以自由字典绕过；
- 若两份真实文件仍存在 review/failed，先回到分卷一修正边界，不得降低质量门禁。

### 默认值

- 不新增依赖；
- S2 未注册或证据不足时维持现有 `unsupported/review_required`，不自动降级为 S1；
- structured 保存元数据值和来源证据；chunks 只复制检索过滤需要的值，不重复整套来源证据；
- 质量门禁新增语义后规则集升级为 `legal-quality-v2`。

### 依赖与包管理工具

- 后端：conda 环境 `fire`，无需新增依赖；
- 前端：不涉及；
- 数据：仅使用 pytest 的 `tmp_path`，禁止写正式 `data/`。

### Task 4：独立注册 S2 并接入统一编排器

**文件：**

- 修改：`app/services/legal_strategy_registry.py`
- 修改：`app/services/legal_ingestion_orchestrator.py`
- 修改：`tests/unit/services/test_legal_strategy_registry.py`
- 修改：`tests/unit/services/test_legal_ingestion_orchestrator.py`

**步骤 1：先写失败测试。**

测试必须固定：

- `build_boundary_strategy_registry(s1_strategy=..., s2_strategy=...)` 分别注册两个内容轴键；
- S2 能解析为 `implemented`，S3 仍为 `unsupported`，S4 仍为 `review_required`；
- 重复注册 S2、kind 不等于 `S2`、使用 tuple/`"W-S2"` 组合键均失败；
- 默认 `run_legal_ingestion()` 对 W-S2 选择现有 W 提取器和 S2 边界策略；
- S2 返回 review/failed 时，不调用结构解析、质量资格或提交；
- W-S1 仍选择原 S1 策略。

**命令执行意图：** 证明默认编排尚未注册 S2，且测试能够识别组合键旁路。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 新增 S2 断言先 FAIL；既有 S1 测试仍 PASS。

**步骤 2：最小接线。**

- 给 `build_boundary_strategy_registry()` 增加可选 `s2_strategy` 参数；
- 在默认编排器中实例化 `S2BoundaryStrategy`；
- 不新增 `Ws2Strategy`、`Ws2IngestionService` 或组合分支；
- 编排顺序仍是分类 → W 提取 → S2 边界 → 结构解析 → 切块 → 质量资格 → 可选提交；
- 结构解析或质量阶段异常继续映射为现有 `failed`，不能伪装成 unsupported。

**命令执行意图：** 验证两个轴独立路由和所有非成功状态的零下游调用。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 全部 PASS；没有组合策略键。

**步骤 3：真实只读编排。**

**命令执行意图：** 对 2 份真实 W-S2 运行 prepare/只读编排，确认能到达 S2 而不产生正式写入。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws2_ingestion_real.py -q
```

**预期输出：** 两份均到达 confirmed S2 中间格式；正式 `data/` 摘要不变。

**Checkpoint：** S2 已能被选择，但在 Task 5—6 通过前不得取得提交资格。

### Task 5：贯通 S2 元数据到 structured 和 chunks

**文件：**

- 修改：`app/services/structure_parser.py`
- 修改：`app/services/chunk_builder.py`
- 修改：`tests/unit/services/test_structure_parser.py`
- 修改：`tests/unit/services/test_chunk_builder.py`
- 修改：`tests/integration/pipeline/test_ws2_ingestion_real.py`

**步骤 1：先写失败测试。**

给 `ParsedDocument` 补充 `revision_events` 和 `metadata_evidence`，测试以下行为：

- S2 的 issuing_authority、promulgated_on、effective_on、revision_events、version_basis 优先取 `intermediate.target`；
- S2 structured 保留 `MetadataEvidence` 的 field/value/source_span/status；
- 前置材料从 body_text 排除后，解析器不能把相关字段重新变成空值；
- S1 的 target 字段为空时，仍允许使用既有纯正文解析结果；
- chunk 继承 issuing_authority、日期、revision_events 和 version_basis；
- chunk 不复制完整 metadata_evidence，避免每个条文重复大量来源数据；
- parsed、中间格式和 chunks 的元数据不一致时 `build_intermediate_chunks()` 拒绝。

**命令执行意图：** 证明当前结构解析会丢失 S2 前置元数据，chunk 也缺少版本字段。

```bash
conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q
```

**预期输出：** 新增元数据传播测试先 FAIL。

**步骤 2：最小实现。**

`parse_legal_intermediate()` 应在完成纯正文条文解析和来源绑定后，用 target 中已确认的值覆盖对应字段；target 为空的字段才沿用现有解析值。不得从 `diagnostics` 或 excluded range 推断元数据。

`build_intermediate_chunks()` 在切块前验证：

- parsed 的 target 值、revision_events、version_basis 与 intermediate 一致；
- metadata_evidence 在 structured 中完整保存；
- 每个 chunk 的检索元数据与 parsed 一致；
- chunk 文本仍只来自 article 和其 paragraph 子单元。

**步骤 3：真实跨层断言。**

两份真实文件必须断言：

- normalized 不含前置材料；
- structured 含 32/37 条和对应元数据证据；
- 所有 chunks 的 document_id、content_class、来源摘要、版本值一致；
- 任一 chunk 文本不含修改决定条号、签署机关列表或发布页日期；
- 河北 structured 保存修订事件和版本依据；
- 社会消防 structured 保存联合机关和公布日期。

**命令执行意图：** 验证真实 W-S2 元数据从来源证据贯通到检索产物，同时正文保持纯净。

```bash
conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/integration/pipeline/test_ws2_ingestion_real.py -q
```

**预期输出：** 全部 PASS；structured 可追溯，chunks 无前置污染。

**步骤 4：回归旧结构化与切块。**

**命令执行意图：** 验证字段扩展没有改变 W-S1 chunk 数量、文本和来源范围。

```bash
conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；W-S1 既有结果稳定。

### Task 6：增加 S2 跨层质量门禁并绑定资格

**文件：**

- 修改：`app/services/legal_quality_gates.py`
- 修改：`app/services/legal_ingestion_orchestrator.py`
- 修改：`tests/unit/services/test_legal_quality_gates.py`
- 修改：`tests/unit/services/test_legal_ingestion_orchestrator.py`
- 新增：`tests/integration/pipeline/test_ws2_legal_corpus_quality.py`

**步骤 1：先写失败门禁矩阵。**

新增两个 S2 专属 gate：

1. `leading_material_isolation`：前置排除范围存在、位于目标标题之前、与 body units/chunks 零重叠，前置条号不进入目标条号集合；
2. `metadata_traceability`：所有已保存元数据值均有合法来源位置，来源块和字符偏移存在，字段值与 intermediate/parsed/chunks 一致。

测试至少覆盖：

- 合法 S2 为 PASS；
- 删除前置排除范围为 FAIL；
- 排除范围与正文重叠为 FAIL；
- 元数据有值无证据为 REVIEW_REQUIRED；
- 证据块序号不存在或字符偏移越界为 FAIL；
- evidence value 与 target 不一致为 FAIL；
- 检测到“修改/修正”信号但无 revision_events/version_basis 为 REVIEW_REQUIRED；
- 检测到多机关联合发布信号但机关或日期无 confirmed 证据为 REVIEW_REQUIRED；
- 任何 review/fail 都不能生成 `CommitQualification`；
- S1 不强制执行 S2 专属 gate，但原通用 gate 全部保留。

质量报告只保存 gate id、测量值和位置引用，不复制前置材料原文。

**命令执行意图：** 证明现有 v1 规则无法识别 S2 前置污染和元数据伪证据。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 新增 S2 gate 测试先 FAIL。

**步骤 2：实现并升级规则集。**

- 将 `RULESET_VERSION` 提升为 `legal-quality-v2`；
- 先运行通用 source/document/boundary/article/body/chunk gate，再按 content class 追加 S2 gate；
- gate 只验证证据，不重新做边界算法；
- `overall=review_required/fail` 时编排器沿用现有零资格、零提交语义；
- 资格摘要必须绑定 v2 完整质量报告，不能复用 v1 摘要。

**步骤 3：两份真实质量矩阵。**

`test_ws2_legal_corpus_quality.py` 从唯一 fixture 派生两份文件，逐文件断言：

- 所有通用 gate PASS；
- 两个 S2 gate PASS；
- overall PASS、ruleset v2；
- article count 分别为 32、37；
- 风险码 `version_metadata` 和 `authority_date_metadata` 对应的字段与证据完整；
- 无 skip、xfail 或缺失时 return。

**命令执行意图：** 用真实源文件证明 S2 不是“切出文本即可”，而是正文与版本证据同时合格。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；两份报告均 overall=pass。

**步骤 4：质量资格与 W-S1 回归。**

**命令执行意图：** 验证新规则集不会放宽资格，也不会破坏 W-S1。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_orchestrator.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** 全部 PASS；W-S1 仍取得 v2 资格，失败路径仍零写入。

## 2. 分卷完成检查

**命令执行意图：** 汇总运行路由、传播、质量和 W-S1 回归。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/unit/services/test_legal_quality_gates.py tests/integration/pipeline/test_ws2_ingestion_real.py tests/integration/pipeline/test_ws2_legal_corpus_quality.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；正式 `data/` 没有变化。

完成证据必须证明：S2 只按内容轴注册；S3/S4 状态不变；元数据跨层一致；所有 S2 值可追溯；质量 v2 阻断伪证据；W-S1 真实回归稳定。本卷完成后才可按总计划执行第二次中文 commit。
