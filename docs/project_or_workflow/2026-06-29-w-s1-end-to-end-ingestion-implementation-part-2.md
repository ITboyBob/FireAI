# W-S1 端到端摄取实施计划（分卷二：Word 提取、S1 边界与解析适配）

> 本计划用于在当前工作区直接分批执行。

**目标：** 分别实现可复用的 W 提取策略与 S1 正文边界策略，通过分卷一的两个注册表组合完成本里程碑处理，形成合法的 `LegalDocumentIntermediate`，再安全适配到现有 `ParsedDocument` 与 chunks。

**架构：** `WordLegalExtractor` 只注册到提取轴的 W 键，`S1BoundaryStrategy` 只注册到内容轴的 S1 键；统一编排器依次解析两个键，禁止创建 W-S1 处理器、组合注册表或专用 CLI。Word 策略只保留候选文本顺序和诊断，不写候选全文；只有 S1 策略产出的 `boundary.status == "confirmed"` 中间格式才能进入现有结构解析与切块链路。

**技术栈：** Python 3.14、标准库 `dataclasses/enum/pathlib/subprocess/typing`、macOS `/usr/bin/textutil`、pytest；所有 Python 和测试命令必须使用 conda 环境 `fire`。

---

## 1. 导航、范围与权威依据

- [W-S1 执行计划总览](./2026-06-29-w-s1-end-to-end-ingestion-implementation.md)
- [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)
- [法规摄取总体架构](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)
- [统一法规摄取入口 ADR](../architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)
- [文件分类与提取器路由设计](../architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md)
- [目标正文边界与统一中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [真实文件评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)

执行本卷时使用 `@tdd-workflow`，严格执行红测、最小实现、绿测、真实上游验证。若本文与专项设计冲突，以专项设计为准。

本卷只实现 W 与 S1 两个独立能力，不实现 PT、PS、S2、S3、S4 自动处理、OCR、质量资格、批次提交或索引更新。PT、PS、S2、S3 的能力状态为 `unsupported`；S4 和证据歧义为 `review_required`；已选策略的确定性执行错误为 `failed`。重复条文、页码域残留等质量问题必须保留为后续门禁可检测的证据，本卷不得用无证据删除来伪造通过。

## 2. Phase 2 启动输入检查

### 已确认项

- 分卷一应先完成 8 份 W-S1 里程碑视图、真实格式探测、双轴分类、共同协议、两个独立注册表及统一编排器。
- 分卷一应提供 `app/services/legal_textutil.py` 的 `run_textutil_stdout()`；该函数只调用 `/usr/bin/textutil` stdout 模式，不清洗、不分类、不持久化。
- `scripts/import_new_corpus.py` 是唯一 CLI；本卷不修改 CLI 或 `run_incremental_import()`，也不创建 W-S1 专用入口。
- Word 无可靠物理分页；本卷必须保留行序、空行证据、块序和逻辑页信息，但不得伪造真实页码。
- 原始 `法律文本/` 只读；整份候选文本只能在进程内短暂存在。
- 现有 `parse_legal_document()` 与 `build_chunks()` 继续兼容旧调用；统一入口的新链路必须走 confirmed 门禁。

### 缺失项

- 若分卷一的 8 文件冻结清单、共同协议、双注册表、统一编排器或低层 `textutil` helper 未完成，本卷停止，不得复制模型或临时建立第二套协议。
- 若 `/usr/bin/textutil` 不存在或不能执行，Task 5 停止并报告环境不兼容，不得安装替代工具。
- 若真实样本路径、摘要或 W-S1 分类与冻结清单不一致，真实验证停止并回到分卷一复核。

### 可采用的默认值

- Word 统一使用 `logical_page=1`、`page_number=None`，并写入“物理分页未知” warning。
- 空行作为边界证据保留；正文规范化只能发生在边界确认之后。
- 标题竞争、第一条缺失、连续条文块不唯一、末条后存在无法分类文本时，默认 `review_required`。
- PT、PS、S2、S3 能力状态为 `unsupported`；S4 为 `review_required`；策略执行错误不得降级成人工复核。
- 本卷真实测试选择 8 份清单中的风险与干净代表样本；8 份逐文件完整验收由分卷四负责。

### 编码前官方文档门禁

- 写任何测试或实现前，先核对本机当前 macOS 的 `textutil(1)` 手册，以及 Python 3.14 官方 `subprocess`、`dataclasses` 文档。
- 需要联网核对时，只能使用 Firecrawl、Exa 或 Tavily MCP，并在执行记录中保存官方页面、访问日期和影响结论；禁止改用通用网页搜索。
- 官方文档若否定 stdout、编码或 subprocess 调用假设，立即停止当前 Task，先修订计划并请求确认，不得私自切换工具。

### 包管理工具与依赖结论

| 运行环境 | 包管理工具 | 本卷结论 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；如获批新增 Python 包才明确使用 conda 或该环境内 pip | 无需新增依赖，禁止安装 |
| 前端 | 不适用 | 不涉及 |
| 其他运行环境 | 不适用；`/usr/bin/textutil` 是既有系统工具，不执行安装 | 不涉及 |

## Task 5：实现 Word 候选提取器

**文件：**

- Create: `app/services/legal_word_extractor.py`
- Modify: `app/services/legal_strategy_registry.py`
- Create: `tests/unit/services/test_legal_word_extractor.py`
- Modify: `tests/unit/services/test_legal_strategy_registry.py`
- Modify: `tests/unit/services/test_legal_ingestion_orchestrator.py`
- Create: `tests/integration/pipeline/test_ws1_ingestion_real.py`
- Reference: `app/services/legal_textutil.py`
- Reference: `app/services/legal_extractor.py`
- Reference: `app/services/legal_source_classifier.py`
- Reference: `app/services/normalizer.py`

**依赖与包管理：**

- 后端：无需新增依赖，使用 conda `fire`，复用 Python 标准库与 `/usr/bin/textutil`。
- 前端：不适用。
- 其他运行环境：不适用；不得安装或切换 Word 转换工具。

### Step 1：检查本 Task 输入

- 已确认项：共同协议导出 `ExtractionRequest`、`ExtractionResult`、`validate_extraction_result()`；请求携带来源摘要和独立分类证据，提取注册表接受 W/PT/PS 键。
- 缺失项：上述对象、`run_textutil_stdout()` 或本机官方手册核对缺失时停止，通知分卷一补齐接缝或先完成文档核对。
- 默认值：`textutil` 输出按原始行序映射为单个逻辑页；warning 不等于质量通过。

**命令执行意图：** 确认既有系统工具和上游模块可用，不执行安装。

```bash
conda run -n fire sh -lc 'test -x /usr/bin/textutil && python -c "import app.services.legal_extractor, app.services.legal_textutil"'
```

**预期输出：** 退出码为 0 且无错误输出；否则停止 Task 5。

### Step 2：编写 Word extractor 红测

测试使用注入的 fake runner 或 monkeypatch 后的 `run_textutil_stdout()`，固定以下行为：

- 命令只能是 `/usr/bin/textutil -convert txt -stdout -encoding UTF-8 <source>`；
- 非零退出、空 stdout 和不可解码输出形成结构化 extraction failure；
- stdout 的原始行序、空行、块序被保留，`page_number` 不被伪造；
- `PAGE \* MERGEFORMAT`、疑似页眉页脚和表格线性化只形成 warning，不在提取层删除；
- `ExtractionResult` 不含输出路径，测试前后临时目录和 `data/` 文件集合不变；
- W 以外的请求被拒绝。
- `WordLegalExtractor` 只能注册到 `ExtractionClass.W`；PT/PS 仍为 `unsupported`，注册表不得接受 `("W", "S1")` 或 `"W-S1"`。

最小红测形态：

```python
result = WordLegalExtractor(run_textutil=fake_textutil).extract(word_request)
assert result.pages[0].page_number is None
assert result.pages[0].logical_page == 1
assert [block.order for block in result.text_blocks] == [0, 1, 2]
assert not hasattr(result, "output_path")
```

**命令执行意图：** 证明 Word extractor 尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_word_extractor.py -q
```

**预期输出：** FAIL，首个错误为无法导入 `app.services.legal_word_extractor` 或缺少 `WordLegalExtractor`。

### Step 3：实现最小 Word extractor

在 `app/services/legal_word_extractor.py` 中实现 `WordLegalExtractor`：

1. 先验证请求为 W 且来源摘要、分类证据完整。
2. 调用上游 `run_textutil_stdout()`，不自行复制 subprocess 命令。
3. 将完整 stdout 只保留在函数调用期间，按原始行映射为 `ExtractedBlock`。
4. 空行保留为边界证据；每个块记录全局 order、逻辑页和行号。
5. 记录退出诊断、字符量、域代码、疑似表格线性化和物理分页未知 warning。
6. 返回共同协议的 `ExtractionResult` 并调用 `validate_extraction_result()`。
7. 不调用 `clean_text()`、`normalize_document()` 或任何 writer。

在统一注册表装配函数中只执行 `extraction_registry.register(ExtractionClass.W, WordLegalExtractor(...))`。不得读取内容分类，不得在类名、注册键或工厂函数中编码 S1。

### Step 4：运行 Word extractor 绿测与回归

**命令执行意图：** 验证 stdout 内存提取、顺序证据、失败模型和零落盘约束，同时保护旧 normalizer。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_word_extractor.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_normalizer.py -q
```

**预期输出：** PASS；W 可独立解析，PT/PS 稳定返回 `unsupported`，旧 normalizer 无回归，测试目录没有新增候选文本文件。

### Step 5：用真实 DOC 与 DOCX 验证提取

在 `tests/integration/pipeline/test_ws1_ingestion_real.py` 参数化：

- `法律文本/todo/事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx`：干净 DOCX 代表；
- `法律文本/todo/督察、处罚与监管/河北省消防技术服务监督管理规定.doc`：带页码域风险的 DOC 代表。

测试必须由冻结清单按 W 轴构造请求，不把 S1 编入 extractor；核对摘要前后不变、标题和第一条可见、逻辑页 warning 存在、候选未写入 `data/` 或临时目录。不得 `skip`、`xfail` 或缺失即返回。

**命令执行意图：** 证明真实 DOC/DOCX 可产生带证据的内存候选。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_ingestion_real.py::test_word_extractor_reads_real_ws1_without_persisting_candidate -q
```

**预期输出：** PASS，2 个参数化样本均通过，原始文件和正式数据目录不变。

**Checkpoint：** 任意证据充分的 W 来源可形成共同协议结果；是否为 S1 不属于 Word 策略职责，“转换成功”没有被提升为正文确认或质量通过。

## Task 6：实现 S1 正文边界与统一中间格式

**文件：**

- Create: `app/services/legal_intermediate.py`
- Create: `app/services/legal_content_boundary.py`
- Modify: `app/services/legal_strategy_registry.py`
- Modify: `app/services/legal_ingestion_orchestrator.py`
- Create: `tests/unit/services/test_legal_intermediate.py`
- Create: `tests/unit/services/test_legal_content_boundary.py`
- Modify: `tests/unit/services/test_legal_strategy_registry.py`
- Modify: `tests/unit/services/test_legal_ingestion_orchestrator.py`
- Modify: `tests/integration/pipeline/test_ws1_ingestion_real.py`

**依赖与包管理：**

- 后端：无需新增依赖，使用 conda `fire` 与 Python 标准库。
- 前端：不适用。
- 其他运行环境：不适用。

### Step 1：检查本 Task 输入

- 已确认项：Task 5 已返回顺序稳定且未持久化的 W `ExtractionResult`；正文边界注册表接受 S1—S4 键。
- 缺失项：来源摘要、唯一 S1 候选、块顺序证据或 Python 3.14 官方模型文档核对缺失时停止，不得从文件名猜正文。
- 默认值：无法唯一确认标题、第一条、连续条文块或末条边界时返回 `review_required`。

### Step 2：编写中间格式与 S1 边界红测

红测必须覆盖：

- 唯一标题与标题后的第一条共同锁定开始位置，不能只取“第一条前最后一行”；
- 章、节和条文块按来源顺序进入正文，条号中断或多个完整候选触发 `review_required`；
- 正文结束于最后一条最后字符，尾随页码域、页脚或印发信息不得进入 `body_text`；
- 末条后出现无法分类的普通文本时不自动确认；
- `LegalDocumentIntermediate` 完整表达 `source_ref`、W、S1、target、boundary、`body_text`、`body_units`、diagnostics 和最小 extraction report；
- `body_units` 单调且位于边界内，`body_text` 由允许单元按序组成；
- 非 confirmed、空正文、无正式条文、摘要变化或正文与排除范围重叠违反不变量；
- `write_confirmed_normalized()` 只把 confirmed `body_text` 写入指定 staging，非 confirmed 时零落盘；
- diagnostics 和报告不得复制排除区域正文。
- `S1BoundaryStrategy` 只能注册到 `ContentClass.S1`，不得检查或要求提取策略键为 W；S2、S3 能力状态保持 `unsupported`，S4 保持 `review_required` 且不得自动 confirmed。

最小红测形态：

```python
intermediate = identify_s1_target_body(extraction, expected_title="河北省火灾事故调查处理规定")
assert intermediate.boundary.status == "confirmed"
assert intermediate.body_text.startswith("河北省火灾事故调查处理规定")
assert "第一条" in intermediate.body_text
validate_legal_intermediate(intermediate)
```

**命令执行意图：** 证明 S1 边界与统一中间格式尚不存在。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py -q
```

**预期输出：** FAIL，缺少中间格式模型或 `identify_s1_target_body()`。

### Step 3：实现最小统一中间格式

在 `app/services/legal_intermediate.py` 中实现不可变模型：

- `SourceSpan`、`BodyUnit`、`TargetMetadata`、`BoundaryDecision`；
- `ExcludedRange`，字段仅含起止位置、类型和原因；
- `ExtractionReport`，不允许保存排除标题、摘要或正文；
- `LegalDocumentIntermediate` 与 `validate_legal_intermediate()`。

校验器逐条实现正文边界设计第 12 节不变量。实现 `write_confirmed_normalized(intermediate, output_dir)`，先校验 confirmed，再以独占文件名写入 `body_text`；失败零落盘。不得提供“先写整份候选再截断”的 writer。

### Step 4：实现最小 S1 边界识别

在 `app/services/legal_content_boundary.py` 中实现 `S1BoundaryStrategy`，并由其 `identify()` 方法复用 `identify_s1_target_body()`：

1. 从独立文本行和冻结清单标题提示生成标题候选。
2. 要求唯一标题之后出现第一条，并识别其后的连续条文块。
3. 保留标题、编、章、节、条和条内段落的来源位置。
4. 综合最后正式条号、终止条款及尾随内容类型确定结束位置。
5. 将已识别页码域、页脚和印发信息记录为范围与原因，不复制其正文。
6. 任一关键证据不唯一时返回 `review_required`，不调用 parser、chunk builder 或 writer。

本 Task 不负责修复重复条文或裁决质量资格；例如第三十三条串入第三十二条的候选必须原样保留，交由分卷三质量门禁阻断。

在正文边界注册表中只注册 `ContentClass.S1`。统一编排器必须先从提取注册表获得 W 策略结果，再从候选结果形成 S1 内容分类，最后独立解析 S1 边界策略；不得新增 `process_ws1()`、组合 factory 或组合注册键。

### Step 5：运行边界绿测

**命令执行意图：** 验证 S1 首尾、来源单调性、排除最小留痕和中间格式不变量。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** PASS；W 与 S1 通过两个注册表组合，S2/S3 fixture 返回 `unsupported`，S4 与歧义 S1 返回 `review_required`，均不误报 confirmed。

### Step 6：真实风险与干净样本验证

在同一集成测试中增加：

- `河北省火灾事故调查处理规定.docx`：干净代表，标题、第一条至第二十七条边界 confirmed；
- `消防监督检查规定.doc`：干净 DOC 代表，标题、第一条至第四十条边界 confirmed；
- `河北省消防安全领域信用管理暂行细则.doc`：尾部 `PAGE \* MERGEFORMAT` 不进入正文；
- `河北省消防行政执法裁量实施办法.doc`：印发信息和页码域不进入第六十二条。

**命令执行意图：** 证明 S1 边界规则同时覆盖干净与尾部污染代表样本。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_ingestion_real.py::test_real_ws1_boundary_covers_clean_and_trailing_risk_samples -q
```

**预期输出：** PASS，4 个参数化样本 confirmed；正文首尾符合基线，报告只保留排除位置、类型和原因。

**Checkpoint：** S1 候选可独立于来源格式形成合法中间格式；本阶段 W 与 S1 的组合来自编排器而非专用处理器。边界 confirmed 只表示正文范围唯一，不表示质量门禁通过。

## Task 7：适配 ParsedDocument、chunks 并完成代表样本链路验证

**文件：**

- Modify: `app/services/structure_parser.py`
- Modify: `app/services/chunk_builder.py`
- Modify: `tests/unit/services/test_structure_parser.py`
- Modify: `tests/unit/services/test_chunk_builder.py`
- Modify: `tests/integration/pipeline/test_ws1_ingestion_real.py`

**依赖与包管理：**

- 后端：无需新增依赖，使用 conda `fire` 与现有测试依赖。
- 前端：不适用。
- 其他运行环境：不适用。

### Step 1：检查本 Task 输入

- 已确认项：Task 6 的 `LegalDocumentIntermediate` 已满足不变量，confirmed 状态可独立验证。
- 缺失项：若 parser 或 chunk builder 需要读取原始 `ExtractionResult`，或编码前官方文档核对未完成，说明边界或流程不合格，停止并修正。
- 默认值：旧 `parse_legal_document()` 和旧结构化 fixture 保持兼容；唯一 CLI 的新链路不允许兼容性旁路。

### Step 2：编写解析与切块红测

测试固定：

- 新增 `parse_legal_intermediate()`，先校验 confirmed，再仅解析 `body_text`；
- `ParsedDocument` 增加带默认值的来源摘要、内容分类、边界状态和版本依据，不破坏旧构造；
- `ParsedArticle` 增加可空 `source_span`；新 W-S1 路径中每条必须绑定对应 `BodyUnit` 来源范围；
- `build_intermediate_chunks()` 只接受 confirmed 中间格式及其 `ParsedDocument`；
- 本里程碑 chunks 携带来源摘要、条文 `source_span`、`extraction_class="W"`、`content_class="S1"`、`boundary_status="confirmed"`；
- `review_required`、摘要不一致或 parser 结果含边界外文本时，structured/chunks writer 均未被调用；
- 旧 `build_chunks()` fixture 继续通过，但不得成为统一摄取新链路的旁路入口。

**命令执行意图：** 证明 confirmed 解析和切块适配尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q
```

**预期输出：** FAIL，新红测缺少 `parse_legal_intermediate()` 或 `build_intermediate_chunks()`。

### Step 3：实现最小解析适配

在 `app/services/structure_parser.py`：

1. 为 `ParsedDocument` 和 `ParsedArticle.source_span` 增加兼容默认字段。
2. 新增 `parse_legal_intermediate()`，先调用 `validate_legal_intermediate()` 并拒绝非 confirmed。
3. 只把 `body_text` 交给现有 `parse_legal_document()`，再合并来源与版本元数据。
4. 按条号与顺序把每个 `ParsedArticle` 绑定到对应 article `BodyUnit.source_span`，断言来源位于 confirmed 正文范围内。

### Step 4：实现最小 chunks 适配

在 `app/services/chunk_builder.py` 新增 `build_intermediate_chunks()`：

1. 同时核对中间格式、`ParsedDocument` 的 document id、摘要和 confirmed 状态。
2. 复用现有 `build_chunks()` 的条内切分，避免建立第二套 chunk 算法。
3. 为新 chunks 补充来源摘要、条文 `source_span`、内容分类和边界状态。
4. 在任何 writer 之前完成门禁；失败不得生成 JSON 或 JSONL。

### Step 5：运行绿测与现有离线链路回归

**命令执行意图：** 验证 confirmed 门禁、元数据传播与旧解析/切块兼容。

```bash
conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/integration/pipeline/test_build_pipeline.py -q
```

**预期输出：** PASS；旧建库链路无回归，唯一 CLI 的新链路不能绕过边界状态。

### Step 6：验证安全与重复风险代表样本

新增端到端但不正式提交的参数化测试：

- `中华人民共和国消防救援衔条例.docx`：干净 DOCX，26 条可解析并覆盖到 chunks；
- `消防产品监督管理规定.doc`：干净 DOC，44 条可解析并覆盖到 chunks；
- `安全生产行政执法与刑事司法衔接工作办法.doc`：候选正文可到达 parser，但第三十二/三十三条异常保持可检测，不在本卷伪修复；
- `河北省消防安全领域信用管理暂行细则.doc`：页码域不得出现在 structured 或 chunks。

测试只在 `tmp_path` 构造中间结果，不调用正式 append-only commit，不写仓库 `data/`。

**命令执行意图：** 证明干净样本可贯通，已知质量风险不会被清洗掩盖。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_ingestion_real.py::test_real_ws1_confirmed_body_reaches_parser_and_chunks_without_hiding_risks -q
```

**预期输出：** PASS，4 个参数化样本均有可回溯结果；重复条文风险仍可供分卷三门禁识别。

**Checkpoint：** W 提取结果经 S1 策略确认后可以安全适配现有 parser/chunks；两个能力仍可独立扩展，质量风险尚未获得提交资格。

## 3. 分卷二完成检查

**命令执行意图：** 汇总验证本卷所有单元、回归与真实代表样本。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_word_extractor.py tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py tests/integration/pipeline/test_ws1_ingestion_real.py -q
```

**预期输出：**

- 所有测试通过，真实测试没有 skip 或 xfail；
- 干净与风险代表样本覆盖 8 份 W-S1 清单中的 DOC、DOCX、尾部污染和重复异常；
- `法律文本/` 摘要不变，仓库正式 `data/` 未新增或修改；
- 整份候选文本没有被持久化；
- 只有 W 和 S1 具备可执行实现，其余稳定键保留显式能力状态，不存在 W-S1 组合策略或专用 CLI；
- S2、S3、PDF、OCR、质量资格和正式提交仍明确未实现。

完成后交给分卷三执行 Word 专属质量门禁与提交资格，并让 `run_incremental_import()` 委托统一编排器；在该接缝完成前不得直接调用唯一 CLI 正式提交。Git 提交范围与提交时点遵循 W-S1 总览；本文不授权 push、回退、切换分支或改写历史。
