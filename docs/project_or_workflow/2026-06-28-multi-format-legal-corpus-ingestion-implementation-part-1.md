# 多格式法律语料摄取分卷一 Implementation Plan

> **状态：已被替代。** 当前任务必须从[法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)进入对应里程碑计划；本文仅用于历史追溯。

> This plan is intended for direct batch execution in the current workspace.

**Goal:** 冻结 `法律文本/todo/` 的 14 份批次输入，并建立可审计的来源模型、真实格式探测和双轴候选分类能力。

**Architecture:** 以只读 `SourceRef` 绑定来源路径和 SHA-256，由清单服务生成不可变批次输入；分类服务先用文件签名与真实 MIME 建立 `SourceProbe`，再把页级证据和内容结构信号映射为 W/PT/PS/PX 与 S1—S4 候选。本文只定义上游共享 DTO 和分类决策，不定义提取器、`LegalDocumentIntermediate`、质量门禁或正式提交。

**Tech Stack:** Python 3.14、标准库 `dataclasses`/`enum`/`hashlib`/`json`/`pathlib`/`subprocess`/`zipfile`、macOS `/usr/bin/file`、现有 `/usr/bin/textutil`、pytest；所有代码与测试使用 conda 环境 `fire`。

**执行技能：** 实施时使用 `@tdd-workflow`；遇到非预期失败时使用 `@systematic-debugging`。

---

## 1. 文档边界与权威输入

- [实施计划总览](./2026-06-28-multi-format-legal-corpus-ingestion-implementation.md)
- [多格式法律语料摄取总设计](../architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)
- [文件分类与提取器路由设计](../architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md)
- [正文边界与统一中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [todo 法律语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)
- [工程技术标准](../architecture_or_strategy/工程技术标准.md)

本文覆盖 Phase 0 和 Task 1—4。后续分卷消费本文固定的 `LegalSourceRecord`，不得把候选分类当成质量门禁已通过。

## 2. 全卷执行约束

1. 开始每个 Task 前复核已确认项、缺失项和默认值。
2. 原始目录只读；不得移动 `todo/`、写入 `done/` 或修改源文件。
3. 新测试先红、最小实现后绿；真实样本测试不得 `skip`、`xfail` 或文件缺失即返回。
4. 本卷不安装依赖。任何新增依赖必须停止执行，先提交依赖清单并取得用户批准。
5. 后端 Python 环境由 conda 管理，包管理命令固定为 `conda run -n fire python -m pip ...`；本卷不执行安装。
6. 获批的 PDF/OCR 命令行工具和语言资源使用 conda 安装到 `fire`；Python 适配包使用该环境内 pip。若候选不支持该边界，停止并请求用户决策。
7. 前端包管理工具：N/A；其他运行环境包管理工具：N/A。
8. Python、pytest 或脚本命令必须以 `conda run -n fire` 开头；不得修改正式 `data/`、索引或增量 manifest。

## Phase 0：阶段输入与依赖审计

### 已确认输入

- `法律文本/todo/` 当前基线为 14 份文件：8 DOC、3 DOCX、3 PDF。
- 分类权威为 W/PT/PS/PX 与 S1—S4；不确定结果必须进入 `review_required`。
- 真实格式以文件签名为主，MIME 和扩展名用于交叉检查。
- 本卷允许使用 Python 标准库、现有 `/usr/bin/file` 与 `/usr/bin/textutil`。
- 附件、评分表和文书模板不检索、不保存；分类诊断不得复制其正文。

### 缺失输入

- PDF 页级字符量和图片覆盖率采集工具的最终选型与用户批准。
- OCR 引擎、中文语言资源、版本、置信度能力和用户批准。

OCR 不属于本卷实现范围。PDF 页级探针只在官方文档调研和用户批准后用于 Task 4 的真实 PDF 分类；未批准时可以完成纯决策单测，但 Task 4 不能宣称真实全量完成。

### 默认值

- 内容摘要：SHA-256。
- 来源路径：相对 `法律文本/todo/` 的 POSIX 路径，按 Unicode 码点排序。
- 候选后缀：`.doc`、`.docx`、`.pdf`，大小写归一化；后缀不决定真实格式。
- 非业务文件：仅忽略明确登记的 `.DS_Store`；其他未知文件进入清单并由分类器判定 PX。
- PDF 初始阈值：有效字符不少于 40 的页面视为文本页；文档级 PT/PS 比例阈值为 80%，图片主导阈值为 50%。阈值必须配置化，不能散落在代码中。

### 依赖审计

**命令执行意图：** 确认所有 Python 后续命令落在 conda 环境 `fire`。

```bash
conda run -n fire python -VV
```

**预期输出：** Python 版本满足 `>=3.14,<3.15`，且命令退出码为 0。

**命令执行意图：** 确认后端包管理工具指向 `fire` 环境内的 pip；不安装任何包。

```bash
conda run -n fire python -m pip --version
```

**预期输出：** 显示 pip 路径位于 conda 环境 `fire`，没有安装行为。

**命令执行意图：** 确认本卷使用的现有系统探针可执行。

```bash
conda run -n fire sh -c 'test -x /usr/bin/file && test -x /usr/bin/textutil'
```

**预期输出：** 无标准输出，退出码为 0；任一工具缺失则停止，不改用未经批准的替代品。

### 官方文档调研与批准门禁

进入真实 PDF 页级探针实现前，使用 Firecrawl、Exa 或 Tavily MCP 查询候选工具的最新官方文档，至少核对：

- 逐页文本字符、图像对象与页面尺寸能否稳定读取；
- 是否提供 Python 3.14 或命令行支持；
- 许可证、macOS 和离线运行边界；
- 安装是否能完全位于 conda 环境 `fire`；
- 工具版本和输出格式能否进入可复现审计。

向用户提交“依赖名、版本范围、用途、安装位置、包管理工具、替代方案、许可证与风险”。未批准前不得安装，也不得把旧探针结果包装成新实现的真实验证。

### Phase 0 checkpoint

- 环境和现有工具审计均有实际输出记录；
- 已明确本卷无需新增依赖；
- PDF/OCR 未批准项被记录为门禁，不被默认接受；
- 若 `fire`、`file` 或 `textutil` 不可用，停止进入 Task 1。

---

### Task 1：冻结 14 文件清单与批次输入

**阶段输入检查：**

- 已确认：根目录为 `法律文本/todo/`，基线文件数为 14，源文件只读。
- 缺失：无。
- 默认值：递归发现、相对路径排序、SHA-256、忽略 `.DS_Store`。

**Files:**

- Create: `app/services/legal_ingestion_models.py`
- Create: `app/services/legal_ingestion_inventory.py`
- Create: `tests/unit/services/test_legal_ingestion_inventory.py`
- Create: `tests/integration/pipeline/test_todo_legal_ingestion_inventory.py`
- Create: `tests/fixtures/legal_ingestion/todo_baseline.json`

**依赖：** 无需新增依赖，使用 Python 标准库；后端包管理工具为 `fire` 环境内 pip，但本 Task 不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

在单元测试中创建乱序、嵌套的 DOC/PDF 和 `.DS_Store`，断言 `freeze_batch_input(root)`：

```python
batch = freeze_batch_input(root)
assert [item.relative_path for item in batch.sources] == ["a.doc", "nested/b.pdf"]
assert all(len(item.source_sha256) == 64 for item in batch.sources)
assert batch.batch_digest == freeze_batch_input(root).batch_digest
```

同时断言源文件内容和摘要在调用前后不变、返回 tuple 不可修改、未知普通文件不会被静默忽略。

真实测试读取 `todo_baseline.json`，直接比较当前目录的 14 个相对路径；缺失、多出或重复时列出差异并失败，不允许 skip。

基线 fixture 的 14 个 `relative_path` 必须逐项来自评估基线，并为每项登记 `expected_extension`、`expected_extraction_class`、`expected_content_class`；不得在测试代码重复维护第二份清单。

**Step 2：运行红测**

**命令执行意图：** 证明清单服务尚不存在或未满足冻结契约。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_inventory.py tests/integration/pipeline/test_todo_legal_ingestion_inventory.py -q
```

**预期输出：** FAIL，原因是模块、模型或 fixture 尚不存在；不得出现 skip。

**Step 3：最小实现**

在 `legal_ingestion_models.py` 定义不可变 `SourceRef` 与 `FrozenBatchInput`：

```python
@dataclass(frozen=True)
class SourceRef:
    relative_path: str
    source_path: Path
    source_sha256: str
    size_bytes: int
    declared_extension: str

@dataclass(frozen=True)
class FrozenBatchInput:
    root: Path
    sources: tuple[SourceRef, ...]
    batch_digest: str
```

在 `legal_ingestion_inventory.py` 实现 `freeze_batch_input(root: Path) -> FrozenBatchInput`。批次摘要只使用排序后的 `relative_path + NUL + source_sha256`，不使用易漂移的 mtime。发现阶段不读取、复制或保存法规正文。

**Step 4：运行绿测**

**命令执行意图：** 验证排序、摘要、不可变输入和未知文件不被静默遗漏。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_inventory.py -q
```

**预期输出：** 单元测试全部 PASS。

**Step 5：真实样本验证**

**命令执行意图：** 证明当前真实清单恰好覆盖 14 份文件且源摘要不变。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_ingestion_inventory.py -q
```

**预期输出：** PASS；输出中无 skipped/xfailed，目录差异为空，运行前后 14 份源文件 SHA-256 完全一致。

**Step 6：checkpoint**

- `FrozenBatchInput.sources` 正好 14 项且顺序稳定；
- 批次摘要可重复；
- 未修改 `法律文本/` 和正式 `data/`；
- 不执行 commit，继续 Task 2。

---

### Task 2：建立来源与分类领域模型

**阶段输入检查：**

- 已确认：下游共享聚合名为 `LegalSourceRecord`；本文不定义提取器或中间正文模型。
- 缺失：无。
- 默认值：候选内容分类允许为空；空值必须伴随 `review_required` 和稳定原因码。

**Files:**

- Modify: `app/services/legal_ingestion_models.py`
- Create: `tests/unit/services/test_legal_ingestion_models.py`
- Modify: `tests/integration/pipeline/test_todo_legal_ingestion_inventory.py`

**依赖：** 无需新增依赖，使用 `dataclasses`、`enum.StrEnum`；后端 pip 不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

固定枚举值、不可变性和聚合不变量：

```python
assert [item.value for item in ExtractionClass] == ["W", "PT", "PS", "PX"]
assert [item.value for item in ContentClass] == ["S1", "S2", "S3", "S4"]
assert LegalSourceClassification(
    extraction_class=ExtractionClass.PS,
    content_class=None,
    disposition=ClassificationDisposition.REVIEW_REQUIRED,
    evidence=(evidence,),
)
```

补充反例：无证据分类、PX 自动继续、S4 自动继续、`content_class=None` 却标记 `continue_processing` 均抛出 `ValueError`。

**Step 2：运行红测**

**命令执行意图：** 证明共享 DTO 和不变量尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_models.py -q
```

**预期输出：** FAIL，原因是枚举或模型不存在。

**Step 3：最小实现**

在同一模型模块新增：

- `ExtractionClass`：W、PT、PS、PX；
- `ContentClass`：S1、S2、S3、S4；
- `ClassificationDisposition`：`continue_processing`、`review_required`、`failed`；
- `ClassificationEvidence`：`code`、`detail`、可选 `page_number`，禁止保存附件正文；
- `PdfPageProbe`：页号、有效字符数、图片覆盖率、文本块数；
- `SourceProbe`：签名类型、真实 MIME、扩展名是否匹配、Word 探针结果、PDF 页探针 tuple、警告；
- `ContentSignals`：唯一目标块、前置材料、尾部排除、交错或歧义；
- `LegalSourceClassification`：双轴候选、disposition、证据与稳定原因码；
- `LegalSourceRecord`：`source_ref`、`probe`、`classification` 的不可变聚合。

所有 `__post_init__` 只校验契约，不推断法规语义。`SourceProbe` 不携带完整提取文本，`ContentSignals` 不保存附件标题或正文。

**Step 4：运行绿测**

**命令执行意图：** 验证共享 DTO 的值域和阻断不变量。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_models.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实样本验证**

**命令执行意图：** 使用真实冻结清单构造 14 个 `SourceRef`，验证路径、摘要和模型序列化字段完整。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_ingestion_inventory.py -q
```

**预期输出：** PASS；14 个来源均可构造共享模型，未读取或保存附件正文。

**Step 6：checkpoint**

- 后续分卷只消费 `LegalSourceRecord`，不另建同义来源 DTO；
- PX、S4 或内容分类缺失不能获得继续处理资格；
- 不执行 commit，继续 Task 3。

---

### Task 3：实现真实文件签名与 MIME 探测

**阶段输入检查：**

- 已确认：DOC 使用 OLE 签名，DOCX 验证 ZIP 内 WordprocessingML 核心项，PDF 验证 `%PDF-`；MIME 使用 `/usr/bin/file` 交叉检查。
- 缺失：无。
- 默认值：签名优先于扩展名；冲突必须记录，不能静默改名。

**Files:**

- Create: `app/services/legal_source_classifier.py`
- Create: `tests/unit/services/test_legal_source_classifier.py`
- Create: `tests/integration/pipeline/test_todo_legal_source_classifier.py`

**依赖：** 无需新增依赖，使用标准库和现有 `/usr/bin/file`；后端 pip 不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

覆盖 PDF 魔数、OLE 魔数、合法 DOCX ZIP、伪装 ZIP、未知格式及后缀冲突：

```python
assert probe_source(pdf_ref).signature_kind == "pdf"
assert probe_source(doc_ref).signature_kind == "ole_doc"
assert probe_source(docx_ref).signature_kind == "wordprocessingml"
assert "extension_mismatch" in probe_source(disguised_ref).warnings
assert probe_source(unknown_ref).signature_kind == "unknown"
```

测试 monkeypatch `/usr/bin/file` 的成功、非零退出、空 MIME 和超时；错误必须转成稳定分类证据，不暴露工具堆栈。

**Step 2：运行红测**

**命令执行意图：** 证明真实格式探测尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** FAIL，原因是 `probe_source` 不存在。

**Step 3：最小实现**

在 `legal_source_classifier.py` 实现：

```python
def detect_signature(path: Path) -> SignatureKind: ...
def detect_mime_type(path: Path) -> str: ...
def probe_source(source_ref: SourceRef) -> SourceProbe: ...
```

`detect_signature` 读取最小必要字节；DOCX 用 `zipfile.ZipFile` 检查 `[Content_Types].xml` 与 `word/document.xml`。`detect_mime_type` 以参数数组调用 `/usr/bin/file -b --mime-type`，设置超时，不使用 shell。探测前后重算 SHA-256；摘要变化立即失败。

**Step 4：运行绿测**

**命令执行意图：** 验证签名优先、MIME 交叉检查和冲突留痕。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实样本验证**

**命令执行意图：** 对真实 14 文件执行只读签名和 MIME 探测。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_source_classifier.py -q
```

**预期输出：** PASS；得到 8 个 `ole_doc`、3 个 `wordprocessingml`、3 个 `pdf`，无文件缺失、无 skip、源 SHA-256 不变。

**Step 6：checkpoint**

- 14 个来源都有机器可读签名、MIME 和冲突警告；
- 扩展名没有被用作真实格式结论；
- 本 Task 未提取法规正文，未写入正式数据；
- 不执行 commit，继续 Task 4。

---

### Task 4：实现 W/PT/PS/PX 与 S1—S4 候选分类

**阶段输入检查：**

- 已确认：提取轴根据探针证据决定；结构轴只根据 `ContentSignals` 形成候选，不按文件名猜测。
- 缺失：真实 PDF 页级探针依赖需经过 Phase 0 官方文档调研和用户批准；PS 的自动 S 分类还需要后续 OCR。
- 默认值：证据不足即 PX 或 `review_required`；PS 未取得 OCR 内容信号时 `content_class=None`。

**Files:**

- Modify: `app/services/legal_source_classifier.py`
- Modify: `tests/unit/services/test_legal_source_classifier.py`
- Modify: `tests/integration/pipeline/test_todo_legal_source_classifier.py`
- Modify: `tests/fixtures/legal_ingestion/todo_baseline.json`

**依赖：** 分类决策本身无需新增依赖。真实 PDF 页级指标只能使用经用户批准且运行于 `fire` 的探针；命令行工具用 conda、Python 适配包用环境内 pip。未批准时不得安装或完成真实 PDF 绿测；前端 N/A；其他环境 N/A。

**Step 1：写红测**

参数化固定分类边界：

```python
assert classify_source(word_probe, s1).extraction_class is ExtractionClass.W
assert classify_source(text_pdf_probe, s2).extraction_class is ExtractionClass.PT
assert classify_source(scan_pdf_probe, None).extraction_class is ExtractionClass.PS
assert classify_source(mixed_probe, ambiguous).extraction_class is ExtractionClass.PX
assert classify_source(word_probe, tail_exclusion).content_class is ContentClass.S3
assert classify_source(word_probe, ambiguous).content_class is ContentClass.S4
```

必须覆盖 79%/80% 文本页边界、79%/80% 扫描页边界、图片覆盖率 49%/50%、扩展名冲突、Word 转换失败、S2 前置材料、S3 尾部排除、S4 交错歧义。断言 PX、S4 和缺失内容信号均为 `review_required`。

**Step 2：运行红测**

**命令执行意图：** 证明双轴候选决策尚未实现。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** FAIL，原因是 `classify_source` 或阈值策略不存在。

**Step 3：最小实现**

新增配置化 `ClassificationThresholds` 和纯函数：

```python
def classify_source(
    probe: SourceProbe,
    content_signals: ContentSignals | None,
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS,
) -> LegalSourceClassification: ...
```

决策顺序必须是：

1. 未知或相互冲突且无法唯一解释的格式 → PX；
2. Word 签名明确且转换探针可用 → W；
3. PDF 文本页比例不低于 80% → PT；
4. PDF 低文本页比例不低于 80%，且其图片覆盖率不低于 50% → PS；
5. 其他 PDF 或混合结果 → PX；
6. `interleaved_or_ambiguous` → S4；
7. 唯一正文块同时有前置材料和尾部排除 → S2，并保留 S3 风险信号；边界不稳定时才是 S4；
8. 仅前置材料 → S2，仅尾部排除 → S3，无两者且目标块唯一 → S1；
9. 无内容信号 → 内容候选为空并 `review_required`。

同时实现 `detect_content_signals(text_preview: str) -> ContentSignals`：只从进程内候选文本生成标题块数量、前置材料、尾部排除和交错歧义信号，不返回或持久化候选正文。“附件”单词本身不得触发截断。

分类证据只保存指标、原因码和页号，不保存候选正文。内容轴只是风险候选，不能替代后续正文边界判断。

**Step 4：运行绿测**

**命令执行意图：** 验证所有阈值边界、分类值域和不确定阻断。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** 全部 PASS，W/PT/PS/PX 与 S1—S4 均有正例和反例。

**Step 5：真实样本验证**

先确认 Phase 0 的 PDF 页级探针已获用户批准；未批准则停止，Task 4 保持未完成。

**命令执行意图：** 对真实 14 文件生成候选分类，并与唯一 baseline fixture 比较。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_source_classifier.py -q
```

**预期输出：** PASS；提取轴为 11 个 W、1 个 PT、2 个 PS；Word 的 S 候选与评估基线一致。PS 在 OCR 未批准时允许 `content_class=None + review_required`，不得按文件名伪造 S2/S3；测试无 skip，14 个源摘要不变。

**Step 6：checkpoint**

- 14 个 `LegalSourceRecord` 均包含来源、探针、分类证据和 disposition；
- W/PT/PS/PX 决策可复现，S1—S4 候选有完整单测；
- PX、S4、PS 内容信号缺失均不能继续正式处理；
- 未定义 extractor 或 `LegalDocumentIntermediate`，未调用 append-only 提交；
- Phase 0 未批准的真实 PDF 探针不得被标记完成。

## 3. 分卷一完成检查

**命令执行意图：** 汇总验证本卷单元与真实集成测试。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_inventory.py tests/unit/services/test_legal_ingestion_models.py tests/unit/services/test_legal_source_classifier.py tests/integration/pipeline/test_todo_legal_ingestion_inventory.py tests/integration/pipeline/test_todo_legal_source_classifier.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；若 PDF 探针尚未批准，必须在 Task 4 checkpoint 前停止，不能运行本命令宣称分卷完成。

完成证据必须同时包括：

- fixture 与当前目录均为 14 文件且集合一致；
- 源文件运行前后 SHA-256 不变；
- 真实签名统计为 8 DOC、3 DOCX、3 PDF；
- 共享 DTO 不保存附件、评分表或文书模板正文；
- 分类不确定时始终为 `review_required`；
- 没有新增依赖、没有正式数据写入。

本卷通过后，按[总览 Git 策略](./2026-06-28-multi-format-legal-corpus-ingestion-implementation.md#6-git-策略)只允许对本卷已验证改动执行一次中文 commit；不授权 push 或历史改写。
