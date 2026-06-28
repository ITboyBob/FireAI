# 多格式法律语料摄取实施计划（分卷二）

> 本计划用于在当前工作区直接分批执行。

**目标：** 建立统一提取器协议、Word/文本型 PDF 提取器、受审批门禁保护的 OCR 适配器，以及只允许目标法规正文进入现有解析和切块链路的统一中间格式。

**架构：** 分卷一产生的 `SourceRef`、W/PT/PS/PX 分类与 S1—S4 候选是本分卷的唯一上游输入。三类提取器只在内存中返回带来源位置的候选结果；正文边界组件随后生成 `LegalDocumentIntermediate`，只有 `confirmed` 正文才能写入 staging 并适配为 `ParsedDocument` 和 chunks。

**技术栈：** Python 3.14、标准库 `dataclasses/enum/pathlib/subprocess/hashlib/typing`、macOS `/usr/bin/textutil`、当前环境已有的 Poppler `pdftotext`、pytest；所有代码和测试使用 conda 环境 `fire`。

---

## 1. 导航与权威依据

- [实施计划总览](./2026-06-28-multi-format-legal-corpus-ingestion-implementation.md)
- [多格式法律语料摄取总设计](../architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)
- [文件分类与提取器路由设计](../architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md)
- [目标正文边界与统一中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)

执行本分卷前必须完成分卷一。不得在本分卷重复定义 `SourceRef`、`ClassificationEvidence`、`SourceProbe`、`LegalSourceClassification`、`LegalSourceRecord`，或 `ExtractionClass`、`ContentClass`、`ClassificationDisposition` 枚举。

## 2. Phase 2 启动输入检查

### 已确认

- conda 环境固定为 `fire`，后端 Python 包使用该环境内的 `python -m pip`；本分卷当前不执行安装。
- Word 继续复用系统 `/usr/bin/textutil`，但不复用会立即写 normalized 文件的 `normalize_document`。
- 当前机器在 `fire` 环境可发现 `/opt/homebrew/bin/pdftotext`，实测版本为 `25.05.0`；执行时必须重新核验。
- 原始 `法律文本/` 只读；附件、评分表、文书模板正文不得写入 normalized、structured、chunks、报告或日志。
- 前端和其他运行环境均不涉及，不使用 npm、pnpm、yarn 或其他包管理工具。

### 缺失输入

- 中文 OCR 引擎、PDF 页面渲染能力和中文语言资源尚未选型、尚未获得安装批准。
- 若执行时 `pdftotext` 不存在，文本 PDF 运行依赖也视为缺失。

### 允许的默认值

- OCR 只实现 adapter、fake 和“未批准即失败”的依赖门禁；不得声称完成真实 OCR。
- `pdftotext` 已存在时不修改 `pyproject.toml`；不存在时停止 Task 7，先向用户报备工具、用途、版本、安装位置和包管理工具。
- 提取器读取到的整份候选文本只能在进程内短暂存在；持久化从 `LegalDocumentIntermediate.body_text` 开始。

## Task 5：定义提取器共同协议

**Files：**

- Create: `app/services/legal_extractor.py`
- Create: `tests/unit/services/test_legal_extractor.py`
- Create: `tests/integration/pipeline/test_legal_extractors_real.py`

**依赖：** 无需新增依赖，沿用 conda `fire` 与 Python 标准库。输入依赖分卷一的 `app/services/legal_ingestion_models.py`。

### Step 1：检查本 Task 输入

- 已确认：分卷一应导出 `SourceRef`、提取分类、内容分类候选和分类证据。
- 缺失项：若上述模型或 14 文件冻结清单测试未完成，停止本 Task。
- 默认值：共同协议不提供磁盘 writer，也不接受 PX 自动提取请求。

### Step 2：编写红测

测试必须固定：

- `ExtractionRequest` 从 `LegalSourceRecord` 完整携带 `SourceRef`、来源摘要、分类证据与 `run_id`；
- `ExtractedPage`、`ExtractedBlock` 保留页号或逻辑页、顺序、原始换行和可选置信度；
- `ExtractionResult` 表达 extractor/version、metrics、warnings、S 类候选、disposition 和 failure；
- PX 请求被拒绝，页面/块顺序错误被契约校验拒绝；
- 模型没有“输出路径”或排除内容正文专用字段。

最小测试形态：

```python
request = ExtractionRequest.from_source_record(source_record, run_id="run-1")
result = FakeExtractor().extract(request)
assert result.source_digest == source_record.source_ref.sha256
assert [block.order for block in result.text_blocks] == [0, 1]
assert not hasattr(result, "output_path")
```

**命令执行意图：** 证明共同协议尚不存在。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_extractor.py -q
```

**预期输出：** FAIL，首个错误为无法导入 `app.services.legal_extractor` 或缺少约定模型。

### Step 3：最小实现

在 `legal_extractor.py` 中实现不可变 dataclass 与 `Protocol`：

```python
class LegalExtractor(Protocol):
    kind: str
    version: str

    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
```

至少定义 `ExtractionRequest`、`SourceLocation`、`ExtractedBlock`、`ExtractedPage`、`ExtractionFailure`、`ExtractionResult` 与 `validate_extraction_result`。位置允许 Word 使用 `page_number=None`，但必须有逻辑页和块顺序；OCR 的 `confidence` 必须是块级字段。所有集合序列化前保持来源顺序。

### Step 4：运行绿测

**命令执行意图：** 验证共同协议、顺序不变量和 PX 拒绝行为。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_extractor.py -q
```

**预期输出：** PASS；没有测试通过临时写文件获得结果。

### Step 5：真实上游验证

在真实测试中从分卷一冻结清单选择一份 Word 文件，构造 request，并核对摘要、真实类型和分类证据保持一致；测试不得 skip。

**命令执行意图：** 证明共同协议可以消费真实 `todo` 清单对象。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py::test_extraction_request_uses_real_frozen_source -q
```

**预期输出：** PASS，源文件摘要在验证前后不变。

**Checkpoint：** 三类提取器已有单一输入输出契约，分卷一模型没有被复制，协议本身不会持久化候选全文。

## Task 6：实现 Word extractor

**Files：**

- Create: `app/services/legal_word_extractor.py`
- Create: `tests/unit/services/test_legal_word_extractor.py`
- Modify: `tests/integration/pipeline/test_legal_extractors_real.py`
- Reference: `app/services/normalizer.py`

**依赖：** 无需新增依赖；复用 `/usr/bin/textutil`。不调用会落盘的 `normalize_document`。

### Step 1：检查本 Task 输入

- 已确认：Task 5 协议已通过，W 请求来自分卷一分类结果。
- 缺失项：`/usr/bin/textutil` 不存在时停止并报告环境不兼容。
- 默认值：Word 无可靠分页时使用一个逻辑页并写入 warning，不伪造页码。

### Step 2：编写红测

测试用注入的 process runner 固定：命令参数、非零退出失败、UTF-8 输出、行序、域代码 warning、逻辑页未知，以及提取前后临时目录文件集合不变。

```python
result = WordLegalExtractor(runner=fake_runner).extract(word_request)
assert result.pages[0].page_number is None
assert result.text_blocks[0].text == "河北省消防设施管理规定"
assert list(tmp_path.rglob("*.txt")) == []
```

**命令执行意图：** 证明 Word extractor 尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_word_extractor.py -q
```

**预期输出：** FAIL，无法导入 extractor。

### Step 3：最小实现

实现 `WordLegalExtractor`：

- 使用 `textutil -convert txt -stdout -encoding UTF-8 <source>`；
- 只捕获 stdout/stderr，不传输出文件路径；
- 将原始行按顺序转换为内存块，保留空行边界证据；
- 记录退出码、字符量、域代码与表格线性化风险；
- 不在本层调用 `clean_text` 删除证据，不判断正文边界。

### Step 4：运行绿测

**命令执行意图：** 验证 Word 转换、诊断和零落盘约束。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_word_extractor.py tests/unit/services/test_normalizer.py -q
```

**预期输出：** PASS，既有 normalizer 测试不回归。

### Step 5：真实上游验证

用真实 `河北省消防设施管理规定.docx` 验证标题和第一条可见、源摘要不变、`data/` 与源目录没有新增产物；此时允许候选结果在内存中包含前置材料，但禁止写出。

**命令执行意图：** 验证真实 Word 上游和 textutil 适配。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py::test_word_extractor_reads_real_todo_without_persisting_candidate -q
```

**预期输出：** PASS，结果带 W 类型、逻辑页 warning 和非空块，源文件未变化。

**Checkpoint：** DOC/DOCX 可形成带顺序证据的内存候选结果；“textutil 成功”未被提升为正文或质量通过。

## Task 7：实现文本型 PDF extractor

**Files：**

- Create: `app/services/legal_text_pdf_extractor.py`
- Create: `tests/unit/services/test_legal_text_pdf_extractor.py`
- Modify: `tests/integration/pipeline/test_legal_extractors_real.py`

**依赖：** 计划复用当前已有 Poppler `pdftotext`，不新增 Python 包。执行前先通过 Firecrawl、Exa 或 Tavily 查询 Poppler 最新官方文档，核对 `-layout`、`-enc UTF-8`、stdout 与分页符语义；此研究不授权安装。

### Step 1：检查本 Task 输入与依赖

- 已确认：Task 5 协议通过，PT 分类已有逐页证据。
- 缺失项：若官方参数核对未完成或二进制不可用，停止实现。
- 默认值：使用 `shutil.which("pdftotext")` 解析路径，不硬编码 Homebrew 路径。

**命令执行意图：** 核对 `fire` 环境实际可用的 PDF 工具。

```bash
conda run -n fire sh -lc 'command -v pdftotext && pdftotext -v'
```

**预期输出：** 返回可执行路径和版本；无输出或非零退出时停止，先请求依赖安装批准。

### Step 2：编写红测

用 fake runner 固定：命令不产生输出文件、`\f` 拆为真实页、页内原始换行保留、页号与块顺序稳定、stderr/乱码/空页进入 warnings，非零退出形成结构化 failure。

```python
result = TextPdfLegalExtractor(runner=fake_runner).extract(pdf_request)
assert [page.page_number for page in result.pages] == [1, 2]
assert result.text_blocks[-1].location.page_number == 2
```

**命令执行意图：** 证明文本 PDF extractor 尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_text_pdf_extractor.py -q
```

**预期输出：** FAIL，无法导入 extractor。

### Step 3：最小实现

执行经官方文档确认的 stdout 模式，以分页符拆页、以原始行为块并记录页号/顺序；只在内存中形成 `ExtractionResult`。不得调用 Word normalizer，不得执行法律段落合并，不得把候选 PDF 全文写入临时报告。

### Step 4：运行绿测

**命令执行意图：** 验证分页、诊断、失败模型和零落盘约束。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_text_pdf_extractor.py -q
```

**预期输出：** PASS。

### Step 5：真实上游验证

使用真实 `中华人民共和国应急管理部令（第7号)社会消防技术服务管理规定.pdf`；验证多页、标题、第四十条、页序和源摘要，禁止 skip。

**命令执行意图：** 证明文本型 PDF 能按页读取真实法规。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py::test_text_pdf_extractor_reads_real_todo_by_page -q
```

**预期输出：** PASS；候选结果含第四十条，未生成 normalized、structured 或 chunks。

**Checkpoint：** PT 文件可形成页级内存候选结果；若执行时缺少 `pdftotext`，本 Task 保持未完成，不能用 mock 绿测替代真实验证。

## Task 8：实现 OCR adapter 与依赖批准门禁

**Files：**

- Create: `app/services/legal_ocr_adapter.py`
- Create: `tests/unit/services/test_legal_ocr_adapter.py`
- Modify: `tests/integration/pipeline/test_legal_extractors_real.py`
- Do not modify: `pyproject.toml`

**依赖：** 当前无需新增依赖。真实 OCR 引擎、PDF 渲染器和中文语言包未批准，禁止安装或假定存在。

### Step 1：检查本 Task 输入

- 已确认：Task 5 协议通过，PS 来源可由分卷一识别。
- 缺失项：真实 OCR 方案、版本、许可证、中文资源、安装位置和包管理工具均未确认。
- 默认值：只实现 `OcrBackend` 协议、fake backend 与显式依赖失败；默认 backend 不存在。

### Step 2：编写红测

测试固定：

- 未批准时在读取或渲染页面前返回 `dependency_not_approved`；
- 只有 `approved=True` 且 backend 自报可用时才允许调用；
- fake backend 的页、块、坐标和块级置信度被无损映射；
- 日志、failure 和 warnings 不包含 OCR 候选正文。

```python
result = OcrLegalExtractor(backend=None, approved=False).extract(ps_request)
assert result.failure.code == "dependency_not_approved"
assert result.text_blocks == ()
```

**命令执行意图：** 证明 OCR 门禁和 adapter 尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ocr_adapter.py -q
```

**预期输出：** FAIL，无法导入 adapter。

### Step 3：最小实现

定义 `OcrBackend` Protocol、`OcrDependencyGate` 和 `OcrLegalExtractor`。adapter 只接受 backend 返回的页级块、坐标、方向与块级置信度；不内置具体 OCR 包名，不读取环境中的偶然可执行文件，不提供“空字符串也算成功”的降级。

若后续要实现真实 backend，必须先暂停并向用户列出：拟安装依赖、用途、准确版本、conda `fire` 内安装位置、包管理工具、中文语言资源、许可证和官方文档证据。获批后再把真实 backend 作为新增 bounded task。

### Step 4：运行绿测

**命令执行意图：** 验证未批准阻断和 fake backend 契约，不验证 OCR 准确率。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ocr_adapter.py -q
```

**预期输出：** PASS。

### Step 5：真实上游门禁验证

将真实扫描件 `廊坊市火灾事故调查处理规定.pdf` 作为 PS 请求，但不执行 OCR；验证门禁在读取页面前失败、源摘要不变且没有候选产物。该测试不是“真实 OCR 通过”。

**命令执行意图：** 证明真实扫描件不会绕过依赖审批。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py::test_scanned_pdf_stops_at_unapproved_ocr_gate -q
```

**预期输出：** PASS，failure 为 `dependency_not_approved`，无持久化正文。

**Checkpoint：** OCR adapter 和审批门禁完成；在用户批准并完成真实 backend 前，PS 真实提取明确未完成，分卷二和最终 14 文件验收不得宣称全部完成。

## Task 9：实现正文边界、统一中间格式与现有解析适配

**Files：**

- Create: `app/services/legal_intermediate.py`
- Create: `app/services/legal_content_boundary.py`
- Create: `tests/unit/services/test_legal_intermediate.py`
- Create: `tests/unit/services/test_legal_content_boundary.py`
- Modify: `app/services/structure_parser.py`
- Modify: `app/services/chunk_builder.py`
- Modify: `tests/unit/services/test_structure_parser.py`
- Modify: `tests/unit/services/test_chunk_builder.py`
- Modify: `tests/integration/pipeline/test_legal_extractors_real.py`

**依赖：** 无需新增依赖。只消费 Task 5 的内存候选结果和分卷一的 S 类候选。

### Step 1：检查本 Task 输入

- 已确认：Task 5 协议、Task 6 和 Task 7 通过；Task 8 adapter 至少能明确阻断未批准 OCR。
- 缺失项：真实 OCR 未批准时，本 Task 不能声称扫描 PDF 边界已经真实验证。
- 默认值：S4、多个同等标题候选、正文与排除范围重叠一律 `review_required`。

### Step 2：编写红测

覆盖：

- S1 唯一标题与连续条文形成 `confirmed`；
- S2 中目标标题之前出现“附件2”时不得提前截断；
- S3 只保留最后一条之前的正文，报告只含排除位置、类型、原因；
- S4、多标题竞争和首尾不唯一禁止 writer、parser 和 chunk adapter；
- 源摘要变化、正文与排除范围重叠、body unit 顺序错误违反不变量；
- `ParsedDocument` 获得来源摘要、内容分类、边界状态和版本元数据；
- `build_chunks` 对显式非 `confirmed` 结构拒绝，同时保持旧结构化 fixture 兼容。

```python
intermediate = identify_target_body(extraction, target_title="河北省消防设施管理规定")
assert intermediate.boundary.status == "confirmed"
assert "第一条" in intermediate.body_text
assert "附件2" not in intermediate.body_text
assert all(not hasattr(item, "text") for item in intermediate.extraction_report.excluded_ranges)
```

**命令执行意图：** 证明边界模型和 confirmed 适配尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py -q
```

**预期输出：** FAIL，缺少中间格式或边界函数。

### Step 3：实现最小中间格式

在 `legal_intermediate.py` 中实现设计文档定义的 `LegalDocumentIntermediate`、`SourceSpan`、`BodyUnit`、`BoundaryDecision`、`TargetMetadata`、`ExcludedRange`、`ExtractionReport` 与不变量校验。`ExcludedRange` 只能有起止位置、类型和原因，类型层面不提供正文属性。

提供 `write_confirmed_body(intermediate, output_dir)`：仅当状态为 `confirmed` 时写 `body_text`；文件内容只允许目标标题、层级标题和条文。

### Step 4：实现最小正文边界

在 `legal_content_boundary.py` 中：

- 先以文件名目标提示、独立标题和其后第一条形成标题候选；
- 按标题后的连续条文块选择目标正文，不能以首次“附件”作为前置截断点；
- 发布/修订材料只转换为带来源位置的元数据；
- 目标正文后的附件、评分表和文书模板只形成 `ExcludedRange`；
- 候选并列、排除范围重叠或 S4 返回 `review_required`，不猜测。

### Step 5：适配 `ParsedDocument` 与 chunks

为 `ParsedDocument` 增加带默认值的来源摘要、内容分类、边界状态、修订事件和版本依据字段，保持现有 `parse_legal_document` 调用兼容。新增 `parse_legal_intermediate()`，先验证 `confirmed`，再只解析 `body_text` 并合并结构化元数据。

为 `build_chunks` 增加显式边界检查：旧 fixture 未带该字段时保持兼容；新结构只允许 `boundary_status == "confirmed"`。新增 `build_intermediate_chunks()` 作为唯一新链路入口。

### Step 6：运行绿测与回归

**命令执行意图：** 验证 S1—S4、排除不持久化、解析适配与既有链路兼容。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q
```

**预期输出：** PASS；既有结构解析和 chunk 测试无回归。

### Step 7：真实上游验证

真实验证至少覆盖：

- `河北省消防设施管理规定.docx`：前置“附件2”不导致目标正文丢失；
- `河北省消防救援机构执法过错责任追究规定.doc`：文书模板不进入 body、structured 或 chunks；
- 真实源文件摘要和目录内容在验证前后不变。

**命令执行意图：** 证明真实 Word 复合文件只生成目标法规正文。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py::test_real_s2_and_s3_only_persist_target_body -q
```

**预期输出：** PASS；排除报告只有位置、类型、原因，所有生成文本均无附件、评分表或模板正文。

**Checkpoint：** W 与 PT 的 confirmed 正文可以安全适配现有 `ParsedDocument/build_chunks`；边界不确定会在正式产物之前失败。PS 只有在真实 OCR 依赖获批并完成后才能达到相同 checkpoint。

## 3. 分卷二完成检查

**命令执行意图：** 汇总验证本分卷全部单元与真实上游测试。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_extractor.py tests/unit/services/test_legal_word_extractor.py tests/unit/services/test_legal_text_pdf_extractor.py tests/unit/services/test_legal_ocr_adapter.py tests/unit/services/test_legal_intermediate.py tests/unit/services/test_legal_content_boundary.py tests/integration/pipeline/test_legal_extractors_real.py -q
```

**预期输出：**

- Word、文本 PDF、共同协议和正文边界相关测试全部通过；
- 真实测试没有 skip 或 xfail；
- OCR 未批准时，依赖门禁测试通过，但计划状态仍明确记录“真实 OCR 未完成”；
- `法律文本/` 摘要不变，附件、评分表和文书模板正文未进入任何持久化产物。

只有上述结果成立，且 Task 8 的真实 OCR 状态被如实记录，才能把分卷二交给分卷三继续实施。当前文档授权执行阶段按总览 Git 策略提交已验证 Phase，但不授权 push 或历史改写。
