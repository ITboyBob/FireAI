# W-S1 端到端摄取实施计划（分卷三：质量资格与 Append-Only 接入）

> 本计划用于在当前工作区直接分批执行；分卷导航与里程碑完成定义见总览。

**目标：** 为 8 份 W-S1 法规建立可审计的质量门禁、逐文件状态、内容绑定提交资格，并安全接入现有单文件 Append-Only 提交。

**架构：** 本卷消费 Task 1—7 产生的冻结清单、独立 W/S1 策略结果、统一中间格式、结构化结果与 chunks。唯一 CLI 调用统一编排器；编排器完成质量资格后逐文件复用现有提交事务，批次层只调度和汇总，不建立跨文件全局事务。

**技术栈：** Python 3.14、标准库 `dataclasses`、`enum`、`hashlib`、`json`、`pathlib`，pytest；运行环境统一为 conda `fire`。

---

## 1. 本卷边界与阶段启动输入检查

### 1.1 已确认项

- 唯一输入基线是 `tests/fixtures/legal_ingestion/todo_baseline.json`；W-S1 范围只能由通用 `select_scope(..., extraction_class=W, content_class=S1)` 过滤得到，不建立第二份清单或组合选择器。
- W-S1 共 8 份真实 Word 文件；源文件只读，测试前后必须校验 SHA-256 不变。
- 上游接口为 `LegalSourceRecord`、`ExtractionResult`、`LegalDocumentIntermediate`、`ParsedDocument` 与 chunks。
- 只有 `auto_passed` 或 `review_passed` 可以获得提交资格；`review_passed` 必须来自人工证据和机械门禁重跑全绿。
- 正式提交继续复用 `commit_staged_import()` 的两次 preflight、独占语料发布、索引备份替换、失败回滚和 manifest 最后写。
- 批次中一份文件失败不阻断其他文件，也不回滚已提交文件；共享正式索引的提交必须串行。
- 本卷无需新增依赖；不执行安装，不执行 Git 提交。

### 1.2 缺失项

- 编码前必须使用 Firecrawl、Exa 或 Tavily 核对 Python 3.14 `dataclasses/hashlib/pathlib`、pytest 及 SQLite 事务相关最新官方文档；未留下版本与契约记录时停止 Task 8。
- 人工复核人员身份系统不在本里程碑范围内；计划只定义可审计的结构化复核记录。

### 1.3 默认值

- 质量规则版本使用显式常量 `legal-quality-v1`，禁止按里程碑命名或隐式使用当前时间作为版本。
- 每个 attempt 的不可变质量报告写入 `data/manifests/legal_ingestion_batches/<batch_id>/<attempt_id>.quality.json`；可变批次汇总只引用其 SHA-256。
- `scripts/import_new_corpus.py` 是唯一薄 CLI；保留位置参数和 `--source`，新增 `--batch-manifest` 并与单文件参数互斥。
- 首版同一批次按冻结清单稳定顺序处理；提取和门禁可逐文件进行，正式 commit 串行执行。

### 1.4 包管理工具

| 运行环境 | 包管理工具 | 本卷处理 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；若未来获准安装 Python 包，使用 `conda run -n fire python -m pip` | 无需新增依赖 |
| 前端 | N/A | 本卷不涉及前端 |
| 其他运行环境 | N/A | 本卷不涉及 Node.js、系统包或 OCR 安装 |

### 1.5 权威依据

- 质量结论、状态机和批次语义以 `docs/architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md` 为准。
- 能力状态以[法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)为准；统一入口和策略路由以[总体架构入口](../architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)与[统一入口 ADR](../architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)为准。
- 提交顺序与回滚语义以 `app/services/incremental_import.py` 和 `docs/project_or_workflow/2026-04-29-append-only-incremental-corpus-import-part-3.md` 为准。
- 本卷不得把“文本非空”“解析成功”或“chunks 非空”当作提交资格。

## Task 8：实现通用与 W 专属质量门禁

**启动输入检查：**

- 已确认：Task 1—7 的接口路径和 `boundary.status == confirmed` 前置条件。
- 缺失：无。
- 默认值：门禁结果按 `fail > review_required > pass` 汇总；合法条号例外必须带来源证据。

**Files:**

- Create: `app/services/legal_quality_gates.py`
- Create: `tests/unit/services/test_legal_quality_gates.py`
- Create: `tests/integration/pipeline/test_ws1_quality_real.py`
- Read: `app/services/legal_ingestion_models.py`
- Read: `app/services/legal_extractor.py`
- Read: `app/services/legal_intermediate.py`
- Read: `app/services/structure_parser.py`
- Read: `app/services/chunk_builder.py`

**依赖与包管理：** 无需新增依赖；后端使用 conda `fire`；前端 N/A；其他运行环境 N/A。

**Step 1：先写失败的单元测试**

固定通用入口 `evaluate_legal_quality(QualityInput) -> QualityReport`；门禁按提取轴与内容轴独立选择，本阶段至少覆盖：

- 唯一标题、正式第一条和 confirmed 边界；
- 条号连续、单调、唯一和条文非空；
- `PAGE \* MERGEFORMAT`、`NUMPAGES`、字段代码、重复页眉页脚、孤立页码和印发尾注；
- 相邻条文串入、相邻条文重复和转换导致的重复正文；
- 中间格式、normalized、structured、chunks 的标题、条号、顺序、来源范围和正文 SHA-256 一致；
- 每条正文都有 chunk，且无重复映射、漏条或正文范围外 chunk；
- 源 SHA-256 变化直接 `fail`，阅读顺序无法证明为 `review_required`。

测试断言稳定的 `gate_id`、结果、测量值和位置证据；不得在失败详情中复制整段法规正文。

**Step 2：运行红测**

**命令执行意图：** 证明当前仓库没有可统一阻断 W-S1 已知污染的门禁入口。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py -q
```

**预期输出：** FAIL，原因是 `legal_quality_gates` 或 `evaluate_legal_quality` 尚不存在。

**Step 3：编写最小实现**

实现不可变模型 `GateOutcome`、`GateResult`、`QualityInput`、`QualityReport`。每个门禁只返回：

```python
@dataclass(frozen=True)
class GateResult:
    gate_id: str
    outcome: GateOutcome
    measured: dict[str, object]
    evidence_refs: tuple[str, ...]
    reason_code: str | None = None
```

`evaluate_legal_quality()` 必须先验证输入都绑定同一 `source_sha256` 和 `document_id`，再按 `extraction_class=W` 选择 Word 门禁、按 `content_class=S1` 选择 S1 门禁，并执行通用和跨层门禁；不得注册 W-S1 组合门禁。正文摘要使用规范化 UTF-8 bytes 计算 SHA-256。

`QualityReport` 必须包含 `ruleset_version`、源摘要、attempt、逐门禁结果、综合结论和报告自身可稳定序列化的摘要输入。机械污染不得被人工豁免。

**Step 4：运行绿测**

**命令执行意图：** 验证门禁结果优先级和所有 W-S1 已知风险均有稳定判定。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py -q
```

**预期输出：** PASS；条号异常为 `review_required`，PAGE 域、页眉页脚污染、串条和跨层不一致为 `fail`。

**Step 5：使用真实 Word 上游产物验证**

真实测试必须经 `WordLegalExtractor.extract()`、`identify_s1_target_body()`、`parse_legal_intermediate()` 和 `build_intermediate_chunks()` 形成输入；禁止直接手写“已清洗文本”冒充上游。

**命令执行意图：** 验证真实 PAGE 域、尾部污染和串条风险能被发现，且源文件保持只读。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_quality_real.py -q
```

**预期输出：** PASS；8 份文件均产生完整报告，已知风险在未修复时被阻断，测试前后 SHA-256 一致，正式 `data/` 未变化。

**完成检查点：** 非 `pass` 报告不能生成提交资格；8 份 W-S1 均执行通用、Word 专属和跨层门禁。

## Task 9：实现逐文件状态机与原子质量报告

**启动输入检查：**

- 已确认：批次 transient 状态必须与 `incremental_imports.json` 分离。
- 缺失：无。
- 默认值：失败重试创建新 attempt；`committed` 是终态；批次允许 `completed_with_exceptions`。

**Files:**

- Create: `app/services/legal_ingestion_batch.py`
- Create: `tests/unit/services/test_legal_ingestion_batch.py`
- Create: `tests/integration/pipeline/test_ws1_batch_report_real.py`

**依赖与包管理：** 无需新增依赖；后端使用 conda `fire`；前端 N/A；其他运行环境 N/A。

**Step 1：先写失败的状态与报告测试**

覆盖合法转换：

```text
discovered -> processing -> auto_passed | review_required | failed
review_required -> processing | review_passed | failed
auto_passed | review_passed -> committing -> committed | failed
failed -> processing
```

另测：`committed` 不可转换；旧 attempt 和 `.quality.json` 不可覆盖；一份失败不改写其他文件；复核缺少 reviewer、时间、源摘要或位置证据时不得 `review_passed`；质量报告拒绝禁止键；临时写入失败不破坏旧报告。

**Step 2：运行红测**

**命令执行意图：** 证明现有 committed-only manifest 不能承担过程状态和门禁证据。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -q
```

**预期输出：** FAIL，原因是状态模型、转换函数或原子报告写入尚不存在。

**Step 3：编写最小实现**

实现 `FileState`、`StateEvent`、`ReviewRecord`、`FileAttempt`、`BatchFileResult`、`BatchReport`、`transition_file()`、`apply_review()`、`write_quality_report_once()` 和 `save_batch_report()`：

- 每次转换追加不可变事件；源摘要或 attempt 不一致即拒绝；
- 人工批准后必须重新调用 `evaluate_legal_quality()`；只有全绿才进入 `review_passed`；
- 每个 attempt 的质量报告采用稳定 JSON 序列化并独占创建，批次汇总只记录其路径和 SHA-256；
- 报告只保存排除范围位置和类型，不保存附件、模板或法规正文副本；
- 使用同目录临时文件加 `Path.replace()` 原子写入；
- 批次汇总不改变任何文件状态，也不写增量 manifest。

**Step 4：运行绿测**

**命令执行意图：** 验证状态约束、失败隔离、复核重跑和报告原子性。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -q
```

**预期输出：** PASS；非法转换无副作用，人工意见不能覆盖机械失败。

**Step 5：使用真实 Word 清单验证**

从唯一 14 项 fixture 和真实 `法律文本/todo/` 冻结清单中过滤 8 份 W-S1，创建并往返读取批次报告；不执行 commit。

**命令执行意图：** 验证报告完整承载真实 W-S1 身份、摘要和逐文件状态。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_batch_report_real.py -q
```

**预期输出：** PASS；恰好 8 份文件初始为 `discovered`，无第二清单，源摘要不变。

**完成检查点：** 逐文件状态和 attempt 可审计；报告原子持久化；manifest 仍只记录 `committed`。

## Task 10：以质量资格收口统一编排器与 Append-Only 提交

**启动输入检查：**

- 已确认：不得重写已有两阶段提交、索引备份回滚和 manifest 最后写语义。
- 缺失：无。
- 默认值：资格必须绑定质量报告、源文件和三类 staged 产物摘要；绑定失配不可重试提交。

**Files:**

- Create: `app/services/legal_qualified_import.py`
- Create: `tests/unit/services/test_legal_qualified_import.py`
- Modify: `app/services/legal_ingestion_orchestrator.py`
- Modify: `app/services/incremental_import.py`
- Modify: `scripts/import_new_corpus.py`
- Modify: `tests/unit/services/test_incremental_import.py`
- Test: `tests/unit/services/test_incremental_manifest.py`
- Modify: `tests/integration/pipeline/test_incremental_import_cli.py`
- Create: `tests/integration/pipeline/test_ws1_qualified_incremental_import.py`

**依赖与包管理：** 无需新增依赖；后端使用 conda `fire`；前端 N/A；其他运行环境 N/A。

**Step 1：先写失败的提交资格测试**

覆盖：

- W-S1 的 `processing`、`review_required`、`failed` 均在第一次 preflight 前被资格适配器拒绝；
- `auto_passed`、`review_passed` 只有摘要全部匹配时可提交；
- 源文件、不可变 attempt 质量报告、normalized、structured 或 chunks 任一摘要变化即拒绝；
- `CommitPlan` 保留真实 `doc`/`docx`，不得在 commit 内伪造成 `docx`；
- 旧位置参数与 `--source` 语法兼容，但未支持、待复核或失败输入在 staging 前零写入；
- `run_incremental_import()` 必须委托统一编排器，不能保留 `normalize → parse → chunks → commit` 旁路；
- 资格通过后两次 preflight 仍各执行一次；
- manifest 写入失败仍恢复三类语料、三类索引和 manifest。

**Step 2：运行红测**

**命令执行意图：** 证明当前 `CommitPlan` 未绑定质量结论，现有 commit 可绕过质量门禁。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_qualified_import.py tests/unit/services/test_incremental_import.py -q
```

**预期输出：** FAIL，原因是 `CommitQualification` 或资格验证入口不存在。

**Step 3：编写最小实现**

新增不可变 `CommitQualification`，至少包含：

```python
@dataclass(frozen=True)
class CommitQualification:
    attempt_id: str
    qualified_state: Literal["auto_passed", "review_passed"]
    ruleset_version: str
    source_sha256: str
    quality_report_sha256: str
    normalized_sha256: str
    structured_sha256: str
    chunks_sha256: str
```

新增 `QualifiedCommitPlan`，组合现有 `CommitPlan`、不可变质量报告路径和 `CommitQualification`。`commit_qualified_staged_import()` 重新计算摘要并验证状态，失败时不调用现有 commit；通过后只调用一次 `commit_staged_import()`。

现有 `CommitPlan` 补充真实 `source_file_type`。`run_incremental_import()` 保留兼容函数签名，但内部只委托 `run_legal_ingestion()`；`scripts/import_new_corpus.py` 也只解析参数、构造请求和呈现稳定结果，不得直接调用 normalizer、parser、chunk builder 或 commit。

资格通过后严格保留现有顺序：

1. 第一次 `validate_append_only_preflight()`；
2. 在独立 staging 中复制并追加关键词与向量索引；
3. 第二次 `validate_append_only_preflight()`；
4. 以独占创建发布 normalized、structured、chunks；
5. 以备份加替换发布 `retrieval.db`、`faiss.index`、`vector_map.json`；
6. 最后写 `incremental_imports.json`；
7. 异常只回滚当前文件，禁止回滚其他已提交文件。

不得把 transient 状态写入现有 manifest，不得把 8 份文件包装成一次全局提交。

**Step 4：运行绿测和回归测试**

**命令执行意图：** 验证质量阻断没有改变现有 Append-Only 与回滚契约。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_qualified_import.py tests/unit/services/test_incremental_import.py tests/unit/services/test_incremental_manifest.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** PASS；未合格输入零正式写入，合格输入保持两次 preflight 和 manifest 最后写。

**Step 5：使用真实 Word 上游产物验证**

在 pytest 临时 `data_dir` 中选取一份真实 W-S1 文件，跑完整上游和门禁，生成资格后调用单文件 commit；再篡改一个 staged 文件验证提交前阻断。

**命令执行意图：** 证明真实 Word 产物能安全复用当前提交事务，内容绑定不可伪造。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_ws1_qualified_incremental_import.py -q
```

**预期输出：** PASS；正常用例的语料、两类索引和 manifest 一致，篡改用例零正式写入，源摘要不变。

**完成检查点：** 唯一 CLI 和兼容服务入口都委托统一编排器；所有正式提交经资格适配器，事务回归保持全绿。

## Task 11：完成唯一 CLI 的单文件与显式批次模式

**启动输入检查：**

- 已确认：范围必须从唯一基线过滤；commit 串行；不做全局事务；不移动 `todo/` 或 `done/`。
- 缺失：无。
- 默认值：保留位置参数与 `--source`；新增 `--batch-manifest`、`--dry-run` 和 `--verify-source-only`。

**Files:**

- Modify: `app/services/legal_ingestion_batch.py`
- Modify: `app/services/legal_ingestion_orchestrator.py`
- Modify: `scripts/import_new_corpus.py`
- Modify: `tests/unit/services/test_legal_ingestion_batch.py`
- Create: `tests/integration/pipeline/test_ws1_batch.py`
- Modify: `tests/integration/pipeline/test_incremental_import_cli.py`

**依赖与包管理：** 无需新增依赖；后端使用 conda `fire`；前端 N/A；其他运行环境 N/A。

**Step 1：先写失败的协调与 CLI 测试**

覆盖：单文件参数与 `--batch-manifest` 互斥；冻结清单后恰好调度 8 份；状态变化原子写报告；单份失败后继续；只有合格文件进入 `committing`；commit 串行；`--dry-run` 不写正式产物；脚本不扫描清单外文件、不移动源文件。

**Step 2：运行红测**

**命令执行意图：** 证明仓库尚无受 W-S1 范围约束的逐文件协调入口。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** FAIL，原因是统一编排器尚未支持批次请求，或 CLI 尚未声明互斥参数。

**Step 3：编写最小协调器与 CLI**

`run_legal_ingestion()` 的批次模式只做：

1. 冻结输入并分别通过提取轴、内容轴注册表选择策略；未注册策略返回 `unsupported`；
2. 每份转为 `processing`，依次执行提取策略、边界策略、中间格式、解析、切块和门禁；
3. 歧义返回 `review_required`，执行错误返回 `failed`，保存状态后继续；
4. 合格文件创建内容绑定资格，转 `committing`，串行调用 `commit_qualified_staged_import()`；
5. 保存 `committed` 或当前文件 `failed`，汇总为 `completed` 或 `completed_with_exceptions`。

`scripts/import_new_corpus.py` 使用互斥参数组：位置参数/`--source` 表示单文件，`--batch-manifest` 引用冻结批次清单。退出码固定为：成功 `0`、执行失败 `1`、参数错误 `2`、未支持 `3`、待复核 `4`；批次含多种结果时返回最严格退出码。

生产默认值不得使用 fake 提取器或 fake embedder。命令输出只包含批次 ID、状态计数和报告路径，不打印法规正文。

**Step 4：运行绿测**

**命令执行意图：** 验证失败隔离、串行提交、退出码和源文件只读契约。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py tests/integration/pipeline/test_ws1_batch.py tests/integration/pipeline/test_incremental_import_cli.py -q
```

**预期输出：** PASS；一份失败不影响其他文件处理，且不存在批次级回滚。

**Step 5：先验证真实 W-S1 源快照**

**命令执行意图：** 在不提取、不提交的前提下验证唯一基线能得到恰好 8 份真实 W-S1。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --verify-source-only
```

**预期输出：** 输出 `selected=8`、冻结清单摘要和批次报告路径，退出码 `0`，无正式产物变化且不打印法规正文。

**Step 6：执行真实 Word dry-run**

**命令执行意图：** 用 8 份真实 Word 文件验证端到端上游、门禁、状态和报告，不发布正式产物。

```bash
conda run -n fire python scripts/import_new_corpus.py --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json --dry-run
```

**预期输出：** 8 份文件均有终止状态和完整质量报告；阻断项明确为 `review_required` 或 `failed`；正式语料、索引和增量 manifest 不变。

**Step 7：运行本卷回归**

**命令执行意图：** 验证新增质量资格未破坏既有单文件导入和上游 W-S1 链路。

```bash
conda run -n fire python -m pytest tests/unit/services tests/integration/pipeline -q
```

**预期输出：** 相关测试全部 PASS；真实测试无 `skip`/`xfail`，8 份源文件 SHA-256 不变。

**完成检查点：** 唯一 CLI 可处理兼容单文件语法和显式批次；无全局事务；三类非成功状态语义稳定，任何未合格文件均无正式产物。

## 2. 本卷完成定义

- 8 份 W-S1 均有可回溯门禁结果、attempt 和终止状态。
- PAGE 域、页眉页脚、印发尾注、相邻条文串入、条文重复、跳号、空条文和跨层不一致均有红绿测试。
- `CommitQualification` 同时绑定源、质量报告和三类 staged 产物；绑定失配在第一次 preflight 前失败。
- 现有两次 preflight、staging 索引副本、独占语料发布、索引备份回滚和 manifest 最后写语义保持不变。
- 批次协调器只做逐文件调度与汇总，不建立 8 文件全局事务，不移动源文件。
- 单元测试通过后，已使用真实上游 Word 产物完成一轮验证；真实测试禁止 `skip`、`xfail` 或文件缺失时静默返回。
- 无新增依赖；所有 Python 和 pytest 命令均通过 conda `fire` 执行。
