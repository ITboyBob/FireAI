# S2 边界能力与 W-S2 组合验收实施计划（分卷一）

> 本卷执行 Task 1—3：先固定事实和契约，再以 TDD 实现 S2 边界。不得修改正式 `data/`。

**目标：** 从唯一 14 文件基线派生 2 项 W-S2 视图，建立带来源位置的元数据证据模型，并让两个真实结构都能形成纯净、可审计的 S2 `confirmed` 中间格式。

**架构：** S2 是独立内容轴策略。它从现有 W `ExtractionResult` 中选择“紧邻完整连续条文”的目标标题，把标题之前的发布与修订材料记录为排除范围，只抽取能够指回来源位置的元数据事实。S1 的既有规则保持不变。

**技术栈：** Python 3.14 标准库、现有领域模型、pytest；全部命令通过 `conda run -n fire` 执行。

---

## 1. 权威输入与本卷边界

- [总计划](./2026-06-30-s2-boundary-and-w-s2-acceptance-implementation.md)
- [能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)
- [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [todo 法规语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)

本卷允许修改中间格式、边界策略及其测试；不得注册 S2、修改 CLI、调用提交服务或写正式索引。

## Phase 1：事实、模型与边界

### 已确认

- 唯一 fixture 为 `tests/fixtures/legal_ingestion/todo_baseline.json`，W-S2 应恰好 2 项；
- `河北省消防设施管理规定.docx` 的目标标题前有政府令、修改决定和 `附件2`，目标正文为 32 条；
- `社会消防安全教育培训规定.doc` 的目标标题出现两次，应选择紧邻正文的后一个标题，正文为 37 条；
- 现有 `TargetMetadata` 的值字段缺少统一来源位置，未完全达到已批准设计；
- 现有 `S1BoundaryStrategy` 不适合重复标题和前置发布材料，不得通过放宽 S1 规则实现 S2。

### 缺失

- 编码前尚需核对 Python 3.14 官方 `dataclasses`、`Enum` 和 `argparse` 契约；本卷 Task 1 负责补齐；
- 两份真实文件的 SHA-256 属于运行时事实，测试必须动态读取，不能写死在计划中。

### 默认值

- 不新增依赖；
- 联合发布机关使用按来源顺序、以中文分号连接的稳定字符串，同时为该值保存覆盖所有签署机关的来源范围；
- 元数据字段无法可靠确认时保留为空并记录诊断，不推测；
- 多个标题候选都满足完整正文条件时返回 `review_required`。

### 依赖与包管理工具

- 后端：conda 环境 `fire`，无需新增依赖；
- 前端：不涉及，不使用 npm、pnpm 或 yarn；
- 系统工具：只读调用现有 `textutil`；
- 联网核验：只能使用 Firecrawl、Exa 或 Tavily 访问 Python 官方文档，不使用通用网页搜索。

### Task 1：冻结 W-S2 派生视图并核验运行时契约

**文件：**

- 新增：`tests/integration/pipeline/test_todo_ws2_scope.py`
- 新增：`docs/reference_material/2026-06-30-s2-runtime-contract-verification.md`
- 修改：`docs/system_meta/文档索引.md`

**步骤 1：先写失败测试。**

测试读取唯一 14 文件 fixture 和真实 `法律文本/todo/`，通过通用条件筛选 W-S2，断言：

- 恰好 2 项，路径分别为总计划中的两份文件；
- article count 分别为 32、37；
- 无重复路径，真实文件均存在；
- 只读探测前后 SHA-256 不变；
- 当前真实分类仍为 `W + S2`；
- 不创建 `ws2_baseline.json` 或 `select_ws2_candidates()`。

**命令执行意图：** 先证明测试能够发现视图数量、路径或分类契约缺失。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws2_scope.py -q
```

**预期输出：** 首次因测试文件尚未实现或缺少通用 W-S2 视图辅助而 FAIL；不能以 skip 代替。

**步骤 2：核对最新官方契约。**

使用允许的联网工具读取 Python 3.14 官方文档，只记录本次会实际使用的结论：

- frozen/slots/kw-only dataclass 的继承与默认值行为；
- `dataclasses.asdict()` 对嵌套 dataclass 和 tuple 的序列化行为；
- Enum 解析非法值时的异常语义；
- `argparse` choice/default 的兼容行为，供分卷三使用。

核验文档必须包含官方链接、访问日期、最小实验命令、结果和对应代码位置；不得复制大段官方原文。若官方契约与计划假设冲突，先停下修改计划。

**步骤 3：实现最小派生视图。**

测试只能从唯一 fixture 过滤：

```python
ws2_records = [
    item
    for item in baseline
    if item["expected_extraction_class"] == "W"
    and item["expected_content_class"] == "S2"
]
```

真实分类继续调用现有探测与分类服务，不在测试里重新写分类算法。

**命令执行意图：** 验证唯一基线、真实目录和当前分类对 2 项 W-S2 的结论一致。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws2_scope.py tests/integration/pipeline/test_legal_source_classifier_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；源摘要不变。

**Checkpoint：** 当前只证明“应该由 W 提取和 S2 处理”，不表示边界已确认、质量已通过或可以提交。

### Task 2：补齐带来源位置的元数据证据模型

**文件：**

- 修改：`app/services/legal_intermediate.py`
- 修改：`tests/unit/services/test_legal_intermediate.py`
- 修改：`tests/unit/services/test_legal_content_boundary.py`

**步骤 1：先增加失败测试。**

新增 `MetadataEvidence` 契约，最小字段为：

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MetadataEvidence:
    field_name: str
    value: str
    source_span: SourceSpan
    extraction_status: Literal["confirmed", "review_required"]
```

在 `TargetMetadata` 增加 `evidence: tuple[MetadataEvidence, ...]`，并固定以下不变量：

- `field_name` 只能对应 `issuing_authority`、`promulgated_on`、`effective_on`、`revision_events` 或 `version_basis`；
- value 和 field_name 不能为空；
- `confirmed` 证据的 value 必须与目标元数据字段一致；`revision_events` 可对应其中一个事件；
- 来源范围起止合法；
- S1 允许证据为空，保持既有中间格式兼容；
- blocked/review 中间格式不得伪造 confirmed 元数据证据。

**命令执行意图：** 证明现有模型无法表达来源位置和提取状态。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py -q
```

**预期输出：** 新测试因 `MetadataEvidence` 或 `TargetMetadata.evidence` 不存在而 FAIL。

**步骤 2：做最小模型实现。**

- 保留现有元数据值字段，避免无关 schema 重写；
- 用 `evidence` 统一关联值、来源位置和提取状态；
- 把 `schema_version` 从 `legal-intermediate-v1` 提升为 `legal-intermediate-v2` 的决定放在创建中间格式的策略中，旧 v1 仅用于读取已有测试对象，不得新生成；
- `validate_legal_intermediate()` 只验证模型内部一致性；“证据是否真的位于原提取块、是否属于排除区域”留给分卷二的跨层质量门禁。

**步骤 3：回归 S1。**

**命令执行意图：** 验证模型扩展没有改变 S1 的标题、条号、尾部排除和来源范围行为。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；8 份真实 W-S1 仍为 confirmed，article count 不变。

**Checkpoint：** 模型此时能表达 S2 证据，但尚无 S2 策略，也不得把元数据证据复制进正文。

### Task 3：TDD 实现 S2 复合发布边界策略

**文件：**

- 新增：`app/services/legal_s2_boundary.py`
- 新增：`tests/unit/services/test_legal_s2_boundary.py`
- 修改：`app/services/legal_content_boundary.py`
- 修改：`tests/unit/services/test_legal_content_boundary.py`
- 新增：`tests/integration/pipeline/test_ws2_ingestion_real.py`

`legal_content_boundary.py` 当前接近 500 行，不应继续堆叠完整 S2 算法。只把 S1/S2 共用且已有测试覆盖的标题规范化、条号解析、body unit 构建等纯函数提取为稳定可复用接缝；S2 主逻辑放在新模块中。禁止复制一套条号解析器。

**步骤 1：写 S2 失败矩阵。**

单元测试至少覆盖：

- 唯一标题 + 前置发布令 + 连续条文；
- 前置修改决定包含“第一条、第二条”等引用时不计入目标正文；
- 目标标题之前出现 `附件2` 时不截断；
- 同名标题出现两次，前一个候选在第一条之前又遇到同名标题，选择后一个；
- 两个候选都拥有独立完整条文时返回 `review_required:title_candidate_ambiguous`；
- 标题后第一条缺失、条号断裂、块顺序非法、源摘要变化分别安全阻断；
- 前置材料与正文来源范围不重叠；
- 元数据证据 span 能指向原始提取块；
- blocked/review 结果不携带正文。

**命令执行意图：** 证明 S2 尚未实现且 S1 不能误处理这些结构。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_s2_boundary.py -q
```

**预期输出：** 因模块或策略不存在而 FAIL。

**步骤 2：实现候选选择。**

`S2BoundaryStrategy(kind="S2")` 必须按以下顺序处理：

1. 校验提取状态、源摘要和块顺序；
2. 找出规范化后等于目标标题的全部候选；
3. 对每个候选，只检查它之后且下一个同名标题之前的第一条和连续条号；
4. 只有一个候选满足“第一条存在、条号连续、正文结束明确”时才确认；
5. 零个或多个可行候选均返回 `review_required`；
6. 使用确认标题到最后一条正文构建 `body_units`；
7. 将标题之前的连续范围登记为 `leading_publication_material` 排除范围；
8. 元数据只从排除范围或标题与第一条之间的明确版本说明中提取，并绑定 `MetadataEvidence`；
9. 调用统一中间格式校验后返回。

不得以“离第一条最近”作为唯一证据，也不得从文件名补全机关或日期。

**步骤 3：固定两个真实结构。**

真实集成测试直接从唯一 fixture 派生 2 项，调用现有 W 提取器和 S2 策略，逐项断言：

- `boundary.status == confirmed`；
- 标题候选位置符合探测事实；
- 文章数分别为 32、37；
- 第一条和最后一条编号正确；
- body_text 不含前置修改决定、签署机关列表或前置同名标题；
- 河北文件的 `附件2` 位于排除范围，不触发正文尾截断；
- 社会消防文件的发布机关和中文数字日期有 confirmed 来源证据；
- 源文件读取前后 SHA-256 相同。

**命令执行意图：** 用两份真实上游文件验证 S2 边界和证据，而非只验证人工构造文本。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_s2_boundary.py tests/integration/pipeline/test_ws2_ingestion_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；2 份文件均 confirmed，正文分别 32、37 条。

**步骤 4：回归 S1 共用函数。**

**命令执行意图：** 证明抽取共用纯函数没有改变 S1 结果。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_content_boundary.py tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS；W-S1 的 8 份真实文件边界和条数不变。

## 2. 分卷完成检查

**命令执行意图：** 汇总运行本卷全部新增与相关回归测试。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_s2_boundary.py tests/integration/pipeline/test_todo_ws2_scope.py tests/integration/pipeline/test_ws2_ingestion_real.py tests/integration/pipeline/test_ws1_ingestion_real.py tests/integration/pipeline/test_ws1_legal_corpus_quality.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；没有正式 `data/` 写入。

完成证据必须证明：无新增依赖；W-S2 视图只有一个事实源；S2 不是组合策略；两个真实正文无前置污染；元数据均有来源位置；S1 回归稳定。本卷完成后才可按总计划执行第一次中文 commit。
