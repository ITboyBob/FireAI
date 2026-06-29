# W-S1 端到端摄取实施计划（分卷一）

> 本计划用于在当前工作区直接分批执行。

**目标：** 冻结唯一 14 文件基线中的 8 份 W-S1 视图，建立可审计的来源模型、真实 Word 探测、双轴策略协议、独立策略注册表和统一摄取编排器，为后续收紧唯一增量导入入口提供稳定接缝。

**架构：** `法律文本/todo/` 仍以唯一 14 文件基线作为机器可读事实源；W-S1 只是里程碑视图，不是运行时组合策略。统一编排器必须先按 W/PT/PS 选择提取策略，再按 S1—S4 选择正文边界策略，禁止注册 `W-S1`、`W-S2` 等笛卡尔积处理器。`scripts/import_new_corpus.py` 保持唯一 CLI；后续分卷让现有 `run_incremental_import()` 委托统一编排器，并在质量资格通过后复用 append-only staging、两次 preflight、回滚和 manifest。

**技术栈：** Python 3.14、标准库 `dataclasses`、`enum`、`hashlib`、`json`、`pathlib`、`subprocess`、`zipfile`，macOS `/usr/bin/file`、`/usr/bin/textutil`，pytest；所有代码和测试使用 conda 环境 `fire`。

**执行技能：** 实施时使用 `@tdd-workflow`；出现非预期失败时使用 `@systematic-debugging`。

---

## 1. 权威输入与本卷边界

- [W-S1 总计划](./2026-06-29-w-s1-end-to-end-ingestion-implementation.md)
- [法规摄取总体架构](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)
- [统一法规摄取入口 ADR](../architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)
- [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)
- [多格式摄取总设计](../architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)
- [分类与提取器路由设计](../architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md)
- [正文边界与中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [todo 14 文件评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)
- [Append-Only 增量导入总览](./2026-04-29-append-only-incremental-corpus-import.md)
- [工程技术标准](../architecture_or_strategy/工程技术标准.md)
- [README 增量导入入口](../../README.md)

本卷覆盖 Task 1—4，不实现 Word 正文提取、S1 正文边界、质量门禁、CLI 参数改造或正式提交。本卷固定统一编排器和两个独立策略注册表的接口；`scripts/import_new_corpus.py` 与 `run_incremental_import()` 的委托改造留给分卷三，禁止新建任何按分类组合命名的 CLI。

## Phase 1：范围冻结与上游契约

### 已确认

- 唯一基线为 `法律文本/todo/` 的 14 份文件；W-S1 视图共 8 份。
- 原始法规目录只读；候选全文不得写入正式 `data/`、报告或日志。
- `scripts/import_new_corpus.py` 是现在及未来的唯一 CLI；现有参数语法保持兼容，但提交行为将在分卷三收紧为“先统一摄取、通过资格后提交”。
- 运行时按两个轴独立路由；W-S1 只能是本里程碑筛选条件，不能成为注册表键或处理器名称。
- 本卷无需新增依赖。

### 缺失

- 无关键产品输入缺失。
- 实施前仍须用 Firecrawl、Exa 或 Tavily 查询 Python 3.14 `dataclasses`、`subprocess`、`zipfile` 与 pytest 当前官方文档；只记录所用版本和契约，不触发安装。

### 默认值

- 摘要算法为 SHA-256；相对路径使用 POSIX 表示并按 Unicode 码点排序。
- 真实格式以签名为首要证据，MIME 交叉检查，扩展名只作声明值。
- `unsupported` 表示所需策略尚未实现；`review_required` 表示候选提取后仍证据不足或需人工判断；`failed` 表示已尝试执行的策略、工具或不变量发生确定性错误。三者都必须零正式写入。

### 依赖与包管理工具

- 无需新增依赖，沿用现有环境。
- 后端运行环境：conda `fire`；Python 包管理工具：`fire` 环境内的 pip，本 Phase 不安装。
- 前端包管理工具：N/A；其他运行环境包管理工具：N/A。

**命令执行意图：** 确认后续 Python 命令运行于合规环境。

```bash
conda run -n fire python -VV
```

**预期输出：** Python 版本满足 `>=3.14,<3.15`，退出码为 0。

**命令执行意图：** 确认包管理工具属于 `fire` 环境，不安装任何包。

```bash
conda run -n fire python -m pip --version
```

**预期输出：** pip 路径位于 conda 环境 `fire`。

**命令执行意图：** 确认现有 Word 和 MIME 探针可执行。

```bash
conda run -n fire sh -c 'test -x /usr/bin/file && test -x /usr/bin/textutil'
```

**预期输出：** 无标准输出且退出码为 0；任一工具缺失时停止本 Phase。

### Task 1：冻结唯一 14 文件基线与 W-S1 视图

**阶段输入检查：**

- 已确认：14 文件名称、扩展名和 W/PT/PS/PX、S1—S4 预期分类来自评估基线。
- 缺失：无。
- 默认值：只忽略明确登记的 `.DS_Store`；其他多出或缺失文件必须失败。

**Files：**

- Create: `tests/fixtures/legal_ingestion/todo_baseline.json`
- Test: `tests/integration/pipeline/test_todo_ws1_scope.py`（Create）
- Read: `docs/reference_material/2026-06-28-todo-legal-corpus-assessment.md`
- Read: `scripts/import_new_corpus.py`
- Read: `app/services/incremental_import.py`
- Read: `tests/unit/services/test_incremental_import.py`
- Read: `tests/integration/pipeline/test_incremental_import_cli.py`

**依赖与包管理工具：** 无需新增依赖；后端使用 conda `fire` 和环境内 pip但不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

测试先读取尚不存在的唯一 fixture，再比较真实目录集合；从 14 项中过滤 W-S1，断言数量为 8、无重复相对路径、源文件读取前后 SHA-256 不变。不得创建 `ws1_baseline.json`、Python 常量列表或第二份同义清单：

```python
ws1 = [
    item for item in baseline
    if item["expected_extraction_class"] == "W"
    and item["expected_content_class"] == "S1"
]
assert len(baseline) == 14
assert len(ws1) == 8
```

**Step 2：运行红测**

**命令执行意图：** 证明唯一基线 fixture 尚未建立。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws1_scope.py -q
```

**预期输出：** FAIL，首个原因是 `todo_baseline.json` 不存在；不得 skip。

**Step 3：建立唯一 fixture**

fixture 每项登记 `relative_path`、扩展名、双轴分类、可空的 `expected_article_count` 和 `risk_codes`。14 项必须是：

| 相对路径 | 提取/内容 | 条数 | 风险码 |
| --- | --- | ---: | --- |
| `事故调查、问责与系统治理/安全生产行政执法与刑事司法衔接工作办法.doc` | W/S1 | 33 | `article_cross_contamination` |
| `事故调查、问责与系统治理/廊坊市消防工作考核办法.pdf` | PS/S3 | - | `ocr_required,tail_table` |
| `事故调查、问责与系统治理/廊坊市火灾事故调查处理规定.pdf` | PS/S2 | - | `ocr_required,leading_notice` |
| `事故调查、问责与系统治理/河北省消防安全领域信用管理暂行细则.doc` | W/S1 | 31 | `word_page_field` |
| `事故调查、问责与系统治理/河北省消防设施管理规定.docx` | W/S2 | 32 | `version_metadata` |
| `事故调查、问责与系统治理/河北省火灾事故调查处理规定.docx` | W/S1 | 27 | - |
| `事故调查、问责与系统治理/社会消防安全教育培训规定.doc` | W/S2 | 37 | `authority_date_metadata` |
| `督察、处罚与监管/中华人民共和国应急管理部令（第7号)社会消防技术服务管理规定.pdf` | PT/S2 | 40 | `page_line_reconstruction` |
| `督察、处罚与监管/中华人民共和国消防救援衔条例.docx` | W/S1 | 26 | - |
| `督察、处罚与监管/河北省消防技术服务监督管理规定.doc` | W/S1 | 30 | `word_page_field` |
| `督察、处罚与监管/河北省消防救援机构执法过错责任追究规定.doc` | W/S3 | 29 | `tail_template,word_page_field` |
| `督察、处罚与监管/河北省消防行政执法裁量实施办法.doc` | W/S1 | 62 | `trailing_print_info,word_page_field` |
| `督察、处罚与监管/消防产品监督管理规定.doc` | W/S1 | 44 | `chunk_structure_overlap` |
| `督察、处罚与监管/消防监督检查规定.doc` | W/S1 | 40 | `chunk_structure_overlap` |

该表用于创建唯一 fixture；实现只能从 14 项 fixture 过滤出 8 项 W-S1，不能再把筛选结果复制进业务代码或测试常量。PDF 分类在本里程碑中只是评估基线元数据，不重新探测，也不据此宣称多格式分卷一完成。

**Step 4：运行绿测与既有链路基线**

**命令执行意图：** 验证真实目录恰为 14 项且 W-S1 视图恰为 8 项。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws1_scope.py -q
```

**预期输出：** PASS，无 skipped/xfailed，目录差异为空。

**命令执行意图：** 记录本卷改动前既有增量导入行为，防止后续误改语义。

```bash
conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** 全部 PASS；单文件限制、冲突失败、staging、回滚和 manifest 行为保持当前基线。

**Checkpoint：** 唯一 14 文件基线可审计，8 项视图只由过滤产生，未调用增量导入、未写正式数据。

### Task 2：建立来源、探针、分类与稳定结果领域模型

**阶段输入检查：**

- 已确认：Task 1 fixture 已通过；来源、探针和双轴分类需使用不可变聚合。
- 缺失：无。
- 默认值：物理提取前允许 `content_class=None`；候选提取后仍无内容信号时为 `review_required`，缺少已识别类别所需策略时为 `unsupported`。

**Files：**

- Create: `app/services/legal_ingestion_models.py`
- Create: `app/services/legal_ingestion_inventory.py`
- Test: `tests/unit/services/test_legal_ingestion_models.py`（Create）
- Test: `tests/unit/services/test_legal_ingestion_inventory.py`（Create）
- Test: `tests/integration/pipeline/test_todo_ws1_scope.py`（Modify）
- Read: `app/services/corpus_ingestor.py`
- Read: `app/services/incremental_import.py`

**依赖与包管理工具：** 无需新增依赖，使用 Python 标准库；后端 conda `fire`、环境内 pip不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

固定 `SourceRef`、`FrozenBatchInput`、`IngestionInput`、`ExtractionClass`、`ContentClass`、`ClassificationDisposition`、`IngestionDisposition`、`ClassificationEvidence`、`SourceProbe`、`ContentSignals`、`LegalSourceClassification`、`LegalSourceRecord` 的值域、不可变性和阻断不变量。`IngestionInput` 要求单文件与冻结批次恰好选择一种；`IngestionDisposition` 至少稳定表达内部 `ready`、`unsupported`、`review_required`、`failed`，后三者都不能携带提交资格。补充清单乱序、嵌套、未知文件、摘要稳定和源文件不变测试。

```python
batch = freeze_batch_input(root)
assert [item.relative_path for item in batch.sources] == ["a.doc", "nested/b.docx"]
assert batch.batch_digest == freeze_batch_input(root).batch_digest
```

**Step 2：运行红测**

**命令执行意图：** 证明共享模型和冻结清单服务尚不存在。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_models.py tests/unit/services/test_legal_ingestion_inventory.py -q
```

**预期输出：** FAIL，原因是模块或类型无法导入。

**Step 3：最小实现**

`SourceRef` 固定 `relative_path`、`source_path`、`source_sha256`、`size_bytes`、`declared_extension`；`freeze_batch_input(root)` 返回排序 tuple 与批次摘要。分类聚合必须拒绝无提取轴证据或 PX 自动继续；内容分类可在物理提取前为空，但候选提取后不得绕过结构轴分类直接进入边界或提交。模型不保存候选正文。

稳定语义必须写入模型注释和测试：策略未注册只能产生 `unsupported`；分类、边界或质量证据不唯一产生 `review_required`；已选择策略后发生工具退出、摘要变化或不变量破坏产生 `failed`。禁止把缺能力包装成失败，也禁止把确定性异常包装成人工复核。

`app/services/legal_ingestion_inventory.py` 只发现和摘要来源，不读取 fixture，也不调用 `resolve_explicit_sources`，避免把现有“单文件提交输入”误用为“批次发现”。

**Step 4：运行绿测**

**命令执行意图：** 验证共享 DTO、清单排序和只读摘要行为。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_models.py tests/unit/services/test_legal_ingestion_inventory.py -q
```

**预期输出：** 全部 PASS。

**Step 5：真实验证**

**命令执行意图：** 用真实上游构造 14 个 `SourceRef` 并与唯一 fixture 比较。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_ws1_scope.py -q
```

**预期输出：** PASS；14 个路径一致、源摘要未变化、未创建 staging。

**Checkpoint：** 后续分卷只消费 `LegalSourceRecord`，不得新增同义来源 DTO 或从文件名推断分类。

### Task 3：实现真实 Word 探测与双轴候选分类

**阶段输入检查：**

- 已确认：Task 2 模型已通过；W 必须由 OLE 或 WordprocessingML 签名、MIME 和非空转换证据共同支持。
- 缺失：无。
- 默认值：签名优先；证据冲突、转换失败或结构歧义均为 `review_required`。

**Files：**

- Create: `app/services/legal_source_classifier.py`
- Create: `app/services/legal_textutil.py`
- Test: `tests/unit/services/test_legal_source_classifier.py`（Create）
- Test: `tests/unit/services/test_legal_textutil.py`（Create）
- Test: `tests/integration/pipeline/test_legal_source_classifier_real.py`（Create）
- Read: `app/services/normalizer.py`
- Read: `app/services/incremental_import.py`
- Read: `docs/architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md`

**依赖与包管理工具：** 无需新增依赖，使用标准库、`/usr/bin/file`、`/usr/bin/textutil`；后端 conda `fire`、环境内 pip不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

覆盖 OLE 魔数、合法 WordprocessingML ZIP、伪装 ZIP、后缀/MIME 冲突、`textutil` 非零退出、空输出和乱码风险。参数化验证 S1、S2、S3、S4 信号；单独出现“附件”不得直接截断或判定 S3。W-S1 仅由清单层通用 `select_scope(records, extraction_class=W, content_class=S1)` 过滤，不得出现 `select_ws1_candidates()` 或组合处理器。

```python
assert probe_source(doc_ref).signature_kind == "ole_doc"
assert probe_source(docx_ref).signature_kind == "wordprocessingml"
assert all(item.classification.content_class is ContentClass.S1 for item in selected)
```

**Step 2：运行红测**

**命令执行意图：** 证明真实探测、双轴候选分类和通用范围过滤尚不存在。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_textutil.py tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** FAIL，原因是 `legal_source_classifier` 无法导入。

**Step 3：最小实现**

在 `legal_textutil.py` 定义 `TextutilRunResult` 与 `run_textutil_stdout(source_path, runner=subprocess.run)`，固定调用 `/usr/bin/textutil -convert txt -stdout -encoding UTF-8`；只捕获 stdout/stderr，接口不接受输出路径，不清洗、不分类、不判边界、不持久化。

在分类服务实现 `detect_signature`、`detect_mime_type`、`probe_source`、`detect_content_signals` 和 `classify_source`，在 inventory 实现轴参数化的 `select_scope()`。DOCX 必须检查 `[Content_Types].xml` 和 `word/document.xml`；外部命令使用参数数组和超时，禁止 shell。候选预览仅在内存中用于信号计算，不进入 DTO、日志或文件。

内容轴只是风险候选：唯一目标法规块、无前置发布材料、无附件/评分表/模板等尾部排除材料且无交错歧义时为 S1。PAGE 域、页码、页脚和印发尾注只形成 W-S1 warning，不改变 S1；最终正文边界仍由下游确认。探测前后重算源摘要，变化立即失败。

**Step 4：运行绿测**

**命令执行意图：** 验证签名优先、MIME 留痕、转换证据和保守分类。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_textutil.py tests/unit/services/test_legal_source_classifier.py -q
```

**预期输出：** 全部 PASS，所有不确定分支均被阻断。

**Step 5：真实验证**

**命令执行意图：** 对真实 11 份 Word 只读探测，并从计算结果筛选 W-S1。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_source_classifier_real.py -q
```

**预期输出：** PASS；8 个 W-S1 候选与唯一 fixture 过滤视图一致，无 skip、无落盘候选、源摘要不变。

**Checkpoint：** W-S1 是两个独立分类结果的可复现视图，不是运行时策略名称、正文确认或质量通过；现有增量导入服务未被调用或修改。

### Task 4：定义双轴策略注册表与统一编排器接缝

**阶段输入检查：**

- 已确认：Task 3 产生包含两个独立分类轴的 `LegalSourceRecord`；唯一 CLI 与 append-only 提交事务继续保留。
- 缺失：W 提取策略和 S1 边界策略由下一分卷实现；PT、PS、S2、S3、S4 本里程碑不实现。
- 默认值：Word 无真实页码时保留逻辑页和 warning，不伪造页号。

**Files：**

- Create: `app/services/legal_extractor.py`
- Create: `app/services/legal_strategy_registry.py`
- Create: `app/services/legal_ingestion_orchestrator.py`
- Test: `tests/unit/services/test_legal_extractor.py`（Create）
- Test: `tests/unit/services/test_legal_strategy_registry.py`（Create）
- Test: `tests/unit/services/test_legal_ingestion_orchestrator.py`（Create）
- Test: `tests/integration/pipeline/test_legal_extractors_real.py`（Create）
- Read: `scripts/import_new_corpus.py`
- Read: `app/services/incremental_import.py`
- Read: `tests/unit/services/test_incremental_import.py`

**依赖与包管理工具：** 无需新增依赖，使用 Python 标准库；后端 conda `fire`、环境内 pip不安装；前端 N/A；其他环境 N/A。

**Step 1：写红测**

固定 `ExtractionRequest`、`SourceLocation`、`ExtractedBlock`、`ExtractedPage`、`ExtractionFailure`、`ExtractionResult`、`LegalExtractor`、`LegalBoundaryStrategy`、两个注册表和 `LegalIngestionOrchestrator`。断言 request 完整携带摘要、分类证据和 `run_id`；结果保持页/块顺序；PX、摘要不匹配和乱序结果被拒绝；协议没有输出路径或正式提交方法。

注册表红测必须证明：

- 提取注册表只接受 W、PT、PS，正文边界注册表只接受 S1、S2、S3、S4；每个稳定键必须有实现或显式能力状态；
- 两个注册表独立解析，不存在 `W-S1`、tuple 或拼接字符串组合键；
- PT、PS、S2、S3 的能力状态为 `unsupported`；
- S4 的能力状态及证据歧义结果为 `review_required`；
- 已选策略抛出确定性工具错误或违反摘要/顺序不变量时返回 `failed`；
- 未提供输入或同时提供单文件与批次时，在解析策略、加载模型或创建 staging 前抛出稳定输入契约错误；
- 三种阻断结果均不调用 writer、`run_incremental_import()` 或 append-only 提交。

**Step 2：运行红测**

**命令执行意图：** 证明共同协议、双注册表与统一编排器尚不存在。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_extractor.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** FAIL，原因是协议模块或类型不存在。

**Step 3：最小实现**

定义不可变 dataclass 与：

```python
class LegalExtractor(Protocol):
    kind: str
    version: str
    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
```

`ExtractionRequest.from_source_record` 接受分类证据充分的 W、PT 或 PS 来源，不绑定 S 类；`ExtractionResult` 只表达来源摘要、extractor 版本、页块、metrics、warnings、disposition 和 failure。本协议不得调用 `generate_new_corpus_artifacts`、`commit_staged_import` 或写 `data/`。

`legal_strategy_registry.py` 分别定义 `ExtractionStrategyRegistry` 与 `BoundaryStrategyRegistry`。编排器按 `record.extraction_class` 解析提取策略，取得候选结果后调用内容结构分类，再按候选的 `content_class` 解析边界策略；不得提供组合注册 API。当前注册表为全部稳定键登记能力状态，但本卷不注册具体实现：W/PT/PS 和 S1/S2/S3 暂为 `unsupported`，S4 固定为 `review_required`。

`LegalIngestionOrchestrator.prepare()` 只运行输入冻结、分类、双轴策略解析和内存处理，返回稳定 outcome；它不加载 embedder、不写 staging、不提交。该方法是阶段内部接缝，不是第二个用户入口；分卷三补齐公开服务入口 `run_legal_ingestion()`，让 `run_incremental_import()` 完整委托，并只把具有提交资格的产物交给现有事务。

**Step 4：运行绿测**

**命令执行意图：** 验证协议值域、独立路由、稳定状态和阻断规则。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_extractor.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py -q
```

**预期输出：** 全部 PASS；fake strategy 不通过临时文件返回结果，不存在组合键，阻断状态零写入。

**Step 5：真实上游与下游回归**

**命令执行意图：** 用真实 W-S1 记录分别解析 W 与 S1 键，证明摘要、分类证据和两个轴不丢失。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_extractors_real.py -q
```

**预期输出：** PASS；当前因具体策略尚未注册而稳定返回 `unsupported`，不提取、不提交、不创建 staging。

**命令执行意图：** 证明新增上游没有改变现有增量导入提交语义。

```bash
conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** 全部 PASS；单文件、preflight、staging、回滚和 manifest 行为与 Task 1 基线一致。

**Checkpoint：** 下一分卷只需分别注册 W 提取策略和 S1 边界策略；只有后续正文、质量资格完成后，统一编排器才可把单份合格产物交给现有 append-only 服务。不得新增分类组合入口。

## 2. 分卷完成检查

**命令执行意图：** 汇总运行本卷全部新增测试。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_models.py tests/unit/services/test_legal_ingestion_inventory.py tests/unit/services/test_legal_textutil.py tests/unit/services/test_legal_source_classifier.py tests/unit/services/test_legal_extractor.py tests/unit/services/test_legal_strategy_registry.py tests/unit/services/test_legal_ingestion_orchestrator.py tests/integration/pipeline/test_todo_ws1_scope.py tests/integration/pipeline/test_legal_source_classifier_real.py tests/integration/pipeline/test_legal_extractors_real.py -q
```

**预期输出：** 全部 PASS，无 skipped/xfailed；真实 14 文件和 8 项视图一致，源摘要不变。

完成证据必须同时证明：无新增依赖；无正式 `data/` 写入；无第二份 W-S1 清单；无分类组合专用 CLI；不存在组合策略键；`unsupported/review_required/failed` 语义稳定；未修改唯一 CLI 和现有提交事务。本卷不执行任何 Git 操作。
