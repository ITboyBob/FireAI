# 多格式法律语料摄取实施计划（分卷三）

> **状态：已被替代。** 当前任务必须从[法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)进入对应里程碑计划；本文仅用于历史追溯。

> This plan is intended for direct batch execution in the current workspace.

**Goal:** 实现提交前质量门禁、逐文件状态与人工复核、批次报告，并把合格产物接入现有单文件 append-only 提交流程。

**Architecture:** 质量层直接消费前两分卷产生的 `LegalSourceRecord`、`ExtractionResult` 和 `LegalDocumentIntermediate`，输出不可被普通警告绕过的质量结论。批次层持久化 transient 状态和复核证据；现有 manifest 仍只记录正式 `committed`，正式索引写入由批次协调器串行调用单文件 commit。

**Tech Stack:** Python 3.14、标准库 `dataclasses/enum/hashlib/json/pathlib/tempfile`、现有 SQLite/FAISS 服务、pytest；所有代码和测试在 conda 环境 `fire` 中执行。

---

> 本分卷入口见[实施计划总览](./2026-06-28-multi-format-legal-corpus-ingestion-implementation.md)。质量规则以[质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)为准，边界与排除契约以[正文边界与统一中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)为准。

## 阶段输入检查

**已确认：**

- 分卷一固定 `LegalSourceRecord`、W/PT/PS/PX 与 S1—S4 分类；
- 分卷二固定 `ExtractionResult`、`LegalDocumentIntermediate` 和 confirmed 边界适配；
- 现有 `incremental_import.py` 已具备两次 preflight、独立 staging、索引副本、回滚和 manifest 最后写入；
- 原始 `法律文本/` 只读，不移动 `todo/` 或 `done/`；
- 不建立 14 文件全局事务。

**缺失项：**

- OCR 引擎、中文语言资源和置信度标定仍待用户批准；
- 缺失项不阻塞 Task 10—13 的协议、Word 真实验证和 fake 测试，但阻塞扫描 PDF 的真实自动通过与正式提交；
- 若 Task 1—9 的类名或字段未按总览落地，先在前序分卷修正，不得在本分卷复制第二套上游模型。

**默认值：**

- OCR 无可靠置信度时，PS 文件只能进入 `review_required`；
- `data/manifests/legal-ingestion-batches/` 保存批次报告，现有 `incremental_imports.json` 只保存 `committed`；
- commit 在单进程协调器中串行执行；并发与跨进程锁不在本分卷范围。

**依赖与包管理：**

- Task 10—14 无需新增依赖，沿用 conda 环境 `fire`；
- 后端若后续获准新增 Python 包，使用 `conda run -n fire python -m pip ...`，但本分卷不得执行安装；
- 前端和其他运行环境不涉及包管理；
- 执行本分卷时使用 `@tdd-workflow`，严格按红测、最小实现、绿测、真实上游验证顺序进行。

## Task 10：实现通用与类型专属质量门禁

**Files:**

- Create: `app/services/legal_quality_gates.py`
- Create: `tests/unit/services/test_legal_quality_gates.py`
- Create: `tests/integration/pipeline/test_legal_quality_real_word.py`
- Read: `app/services/legal_ingestion_models.py`、`app/services/legal_extractor.py`、`app/services/legal_intermediate.py`
- Read: `app/services/structure_parser.py`、`app/services/chunk_builder.py`

**依赖：** 无需新增依赖；复用 Task 1—9 的模型、现有 pytest 和真实 Word 提取链路。OCR 门禁只消费适配器指标，不安装 OCR。

**Step 1: Write the failing unit tests**

定义统一入口 `evaluate_quality(QualityInput) -> QualityReport`，先固定以下失败样本：

```python
@pytest.mark.parametrize(
    ("case_name", "gate_id", "decision"),
    [
        ("duplicate_article", "article_unique", "review_required"),
        ("empty_article", "article_nonempty", "review_required"),
        ("word_page_field", "word_field_clean", "fail"),
        ("missing_pdf_body_page", "body_page_coverage", "fail"),
        ("low_ocr_article_confidence", "ocr_critical_confidence", "review_required"),
        ("s3_excluded_overlap", "excluded_range_isolation", "fail"),
    ],
)
def test_quality_gate_blocks_known_risks(case_name, gate_id, decision, quality_cases):
    report = evaluate_quality(quality_cases[case_name])
    assert report.decision == decision
    assert next(item for item in report.gates if item.gate_id == gate_id).outcome == decision
```

另加自动通过、源 SHA-256 变化、条号合法例外、PT 硬换行、PS 无置信度、S2 版本证据、S3 排除正文和跨层 chunk 越界测试。测试构造器只能组装前序 DTO，不得另建影子模型。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明当前仓库没有统一门禁及三类判定。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py -q
```

**预期输出：** FAIL，原因是 `legal_quality_gates` 或 `evaluate_quality` 尚不存在。

**Step 3: Write the minimal implementation**

在新模块中定义：

```python
class GateOutcome(StrEnum):
    PASS = "pass"
    REVIEW_REQUIRED = "review_required"
    FAIL = "fail"
@dataclass(frozen=True)
class GateResult:
    gate_id: str
    outcome: GateOutcome
    measured: dict[str, object]
    evidence_refs: tuple[str, ...]
    reason_code: str | None = None
@dataclass(frozen=True)
class QualityReport:
    ruleset_version: str
    source_sha256: str
    decision: GateOutcome
    gates: tuple[GateResult, ...]
```

`QualityInput` 只引用 `LegalSourceRecord`、`ExtractionResult`、`LegalDocumentIntermediate`、`ParsedDocument`、normalized 正文和 chunks。按设计注册并执行：

- 通用：源摘要、confirmed 边界、100% 正文页/块覆盖、第一条、连续/唯一/非空、跨层摘要、chunk 覆盖、排除范围隔离；
- Word：PAGE/NUMPAGES/HYPERLINK 域、重复页眉页脚、相邻条文串入与重复；
- PT：目标页非空、页序、分页断行、跨页条文和来源坐标；
- PS：逐页覆盖、页面与关键条号置信度；阈值按引擎和规则版本读取，无置信度不得自动通过；
- S2：唯一标题—条文块、前置材料隔离、版本事实来源；
- S3：正文与排除范围不相交，所有持久化候选中不含排除正文。

综合结果按 `fail > review_required > pass` 取最严格值。`GateResult` 只允许位置引用和测量值，不允许保存附件、评分表或模板文本。

**Step 4: Run unit tests to verify they pass**

**命令执行意图：** 验证全部门禁、结果优先级和报告最小化。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_quality_gates.py -q
```

**预期输出：** PASS，三类结果及所有已知风险均有稳定 `gate_id`。

**Step 5: Verify with real upstream Word artifacts**

真实测试通过 Task 5—9 处理 `河北省火灾事故调查处理规定.docx` 和一个已知 PAGE 域样本，断言前者形成完整结论、后者在污染未清理时被阻断；文件缺失必须失败，不得 skip。

**命令执行意图：** 用真实来源证明门禁消费的不是手工伪造文本。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_quality_real_word.py -q
```

**预期输出：** PASS，源文件测试前后 SHA-256 一致，未写正式 `data/`。

**Step 6: Record the checkpoint**

**Checkpoint：** `fail/review_required` 不能生成提交资格；Word、PT、PS、S2、S3 均有测试；未批准 OCR 不会自动通过。

## Task 11：实现逐文件状态机与原子批次报告

**Files:**

- Create: `app/services/legal_ingestion_batch.py`
- Create: `tests/unit/services/test_legal_ingestion_batch.py`
- Create: `tests/integration/pipeline/test_legal_ingestion_batch_real.py`

**依赖：** 无需新增依赖；使用标准库 JSON、临时文件原子替换和 Task 1 的冻结清单。

**Step 1: Write the failing tests**

固定 `discovered → processing → auto_passed/review_required/failed → committing → committed`，并覆盖：

```python
def test_committed_is_terminal(batch_report):
    committed = transition(batch_report, "source-1", FileState.COMMITTED)
    with pytest.raises(InvalidStateTransition):
        transition(committed, "source-1", FileState.PROCESSING)

def test_one_file_failure_does_not_change_other_file(batch_report):
    updated = transition(batch_report, "source-1", FileState.FAILED)
    assert updated.files["source-2"].state == FileState.DISCOVERED
```

另测原子 JSON 写入、attempt 历史不可覆盖、`completed_with_exceptions` 不等于阶段完成、报告拒绝排除正文键值。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明当前 manifest 不能承担 transient 批次状态。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -q
```

**预期输出：** FAIL，原因是批次状态模型和持久化服务不存在。

**Step 3: Write the minimal implementation**

实现 `FileState`、`BatchState`、`StateEvent`、`FileAttempt`、`BatchFileResult`、`BatchReport`，并把合法转换固定为常量：

```python
ALLOWED_TRANSITIONS = {
    FileState.DISCOVERED: {FileState.PROCESSING},
    FileState.PROCESSING: {FileState.AUTO_PASSED, FileState.REVIEW_REQUIRED, FileState.FAILED},
    FileState.REVIEW_REQUIRED: {FileState.PROCESSING, FileState.REVIEW_PASSED, FileState.FAILED},
    FileState.AUTO_PASSED: {FileState.COMMITTING},
    FileState.REVIEW_PASSED: {FileState.COMMITTING},
    FileState.COMMITTING: {FileState.COMMITTED, FileState.FAILED},
    FileState.FAILED: {FileState.PROCESSING},
    FileState.COMMITTED: set(),
}
```

`save_batch_report` 必须先写同目录临时文件再 `Path.replace()`；每次转换追加事件，不原地覆盖旧 attempt。报告记录源摘要、分类、提取器、门禁、排除位置、人工复核、commit 和错误字段，但不记录排除文本。

**Step 4: Run unit tests to verify they pass**

**命令执行意图：** 验证状态转换、失败隔离和报告原子性。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -q
```

**预期输出：** PASS，非法转换失败且不会产生半份报告。

**Step 5: Verify with the real frozen inventory**

集成测试从真实 `todo/` 读取恰好 14 个 `LegalSourceRecord`，创建初始报告并重新读取，断言相对路径、SHA-256 和状态齐全；不执行提取或提交。

**命令执行意图：** 验证批次报告可以完整承载真实清单。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_ingestion_batch_real.py::test_real_inventory_round_trips_batch_report -q
```

**预期输出：** PASS，14 个文件均为 `discovered`，源摘要未变化。

**Step 6: Record the checkpoint**

**Checkpoint：** transient 状态与 committed-only manifest 分离；attempt 历史不可覆盖；单份失败不改写其他文件状态。

## Task 12：实现人工复核记录与重新门禁

**Files:**

- Modify: `app/services/legal_ingestion_batch.py`
- Modify: `tests/unit/services/test_legal_ingestion_batch.py`
- Modify: `tests/integration/pipeline/test_legal_ingestion_batch_real.py`

**依赖：** 无需新增依赖；复用 Task 10 的 `evaluate_quality`。不引入账号、签名或远程审批系统。

**Step 1: Write the failing tests**

覆盖批准、否决、源摘要变化、缺复核人、缺位置证据和“批准后机械门禁仍失败”：

```python
def test_review_approval_requires_green_gate_rerun(review_required_report, review_record):
    updated = apply_review(
        review_required_report,
        review_record,
        rerun_quality=lambda: quality_report("fail"),
    )
    assert updated.file.state == FileState.FAILED
    assert updated.file.state != FileState.REVIEW_PASSED
```

复核记录只允许 `reviewer`、`reviewed_at`、`decision`、`reason_code`、`evidence_refs` 和 `source_sha256`；测试必须拒绝正文、附件标题、OCR 文本或自由复制内容。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明当前没有可审计复核，也不能阻止“人工直接放行”。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -k review -q
```

**预期输出：** FAIL，原因是 `ReviewRecord` 或 `apply_review` 尚不存在。

**Step 3: Write the minimal implementation**

实现不可变 `ReviewRecord` 与 `apply_review`：

- 只接受当前状态为 `review_required` 且源 SHA-256 一致的记录；
- `reject` 转为 `failed`；
- `approve` 必须重新执行 Task 10 全部门禁；
- 重跑为 `pass` 才转 `review_passed`，重跑为 `review_required` 则保持待复核，重跑为 `fail` 则失败；
- 保存复核人与位置证据，不保存附件或模板文本；
- 任何复核不得直接写现有增量 manifest。

**Step 4: Run unit tests to verify they pass**

**命令执行意图：** 验证复核证据和重新门禁不可绕过。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py -q
```

**预期输出：** PASS，只有复核后机械门禁全绿才能得到 `review_passed`。

**Step 5: Verify against a real review-prone source**

使用真实 `廊坊市消防工作考核办法.pdf` 的路径和 SHA-256 构造仅含页码位置的复核记录，验证报告可往返且源摘要不变；OCR 未批准时不得断言其已通过。

**命令执行意图：** 验证复核记录绑定真实源但不复制评分表。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_legal_ingestion_batch_real.py::test_review_record_binds_real_source_without_excluded_text -q
```

**预期输出：** PASS，报告无排除正文，文件保持 `review_required` 或按真实门禁结果转换。

**Step 6: Record the checkpoint**

**Checkpoint：** 复核证据最小且可审计；人工意见不能覆盖机械失败；review 状态不进入正式 manifest。

## Task 13：把质量资格接入现有单文件 append-only 提交

**Files:**

- Modify: `app/services/legal_quality_gates.py`
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`
- Create: `tests/integration/pipeline/test_qualified_incremental_import.py`
- Test: `tests/unit/services/test_incremental_manifest.py`

**依赖：** 无需新增依赖；复用现有 preflight、staging、关键词/向量追加、回滚和 manifest。真实验证使用现有 `FakeEmbedder`。

**Step 1: Write the failing tests**

先固定四条提交不变量：

```python
@pytest.mark.parametrize("state", ["processing", "review_required", "failed"])
def test_commit_rejects_unqualified_state(state, qualified_plan_factory):
    plan = qualified_plan_factory(state=state)
    with pytest.raises(IncrementalImportError, match="质量门禁未通过"):
        commit_staged_import(plan, embedder=FakeEmbedder())
    assert_formal_outputs_unchanged(plan)
```

另测源摘要变化、质量报告摘要变化、staged 三类语料摘要变化、真实来源类型未被伪造成 docx、preflight 仍执行两次、manifest 仍最后写、manifest 失败仍完整回滚。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明现有 commit 可在没有质量资格时直接发布。

```bash
conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py -k "qualified or rollback or preflight" -q
```

**预期输出：** FAIL，原因是 `CommitPlan` 没有质量资格或 commit 未验证它。

**Step 3: Write the minimal implementation**

在质量模块定义 `CommitQualification`，至少绑定：

- `source_sha256`；
- `quality_report_sha256` 与合格状态 `auto_passed/review_passed`；
- normalized、structured、chunks 的逐文件 SHA-256；
- `ruleset_version` 和 attempt 标识。

修改 `CommitPlan` 强制携带 `CommitQualification` 和真实媒体类型。`commit_staged_import` 的第一步验证当前源摘要、质量报告摘要、三类 staged 产物摘要和合格状态；任一不一致时在 preflight 和正式写入前失败。

保留现有提交顺序：资格验证 → 第一次 preflight → staging 索引副本 → 第二次 preflight → 独占发布语料 → 带备份替换索引 → manifest 最后写；异常只回滚当前文件。

将 preflight 的内部输入收敛为 `document_id`，删除 commit 中伪造 `file_type="docx"` 的做法。现有 manifest schema 不增加 transient 状态，只继续追加 `committed`。

**Step 4: Run unit and regression tests**

**命令执行意图：** 验证质量阻断没有破坏现有 append-only 与回滚语义。

```bash
conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/unit/services/test_incremental_manifest.py -q
```

**预期输出：** PASS，未合格产物零正式写入，合格产物保持原有事务顺序。

**Step 5: Verify with a real qualified Word source**

在临时 `data_dir` 中使用真实 `河北省火灾事故调查处理规定.docx` 跑 Task 1—10，生成资格后调用单文件 commit；断言正式语料、两类索引与 manifest 一致，原始文件摘要不变。

**命令执行意图：** 证明真实上游产物可以穿过资格检查并复用现有提交。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_qualified_incremental_import.py -q
```

**预期输出：** PASS；故意篡改任一 staged 文件的对照用例在正式写入前失败。

**Step 6: Record the checkpoint**

**Checkpoint：** commit 需要内容绑定资格；两次 preflight、staging、回滚、manifest 顺序不变；PDF 不再伪装为 docx。

## Task 14：实现批次协调器与脚本入口

**Files:**

- Modify: `app/services/legal_ingestion_batch.py`
- Create: `scripts/import_todo_corpus.py`
- Modify: `tests/unit/services/test_legal_ingestion_batch.py`
- Create: `tests/integration/pipeline/test_todo_corpus_batch.py`
- Create: `tests/integration/pipeline/test_import_todo_corpus_cli.py`

**依赖：** 无需新增依赖；使用标准库 `argparse` 和现有 `Settings`。真实 PS 自动提交继续受已批准 OCR 依赖门禁约束。

**Step 1: Write the failing coordinator and CLI tests**

覆盖：

- 冻结清单后逐文件处理；某文件失败后继续；
- 只有 `auto_passed/review_passed` 才按稳定顺序串行 commit；
- 后续失败不回滚已提交文件；每次状态变化原子刷新报告；
- `--dry-run` 不写正式产物；
- `--verify-source-only` 只校验冻结 SHA-256；
- 脚本不移动 `todo/` 或 `done/`。

核心失败隔离测试：

```python
def test_batch_continues_after_one_file_fails(batch_dependencies):
    batch_dependencies.processor.fail_on("source-2")
    result = run_todo_batch(batch_dependencies)
    assert result.files["source-1"].state == FileState.COMMITTED
    assert result.files["source-2"].state == FileState.FAILED
    assert result.files["source-3"].state == FileState.COMMITTED
```

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明仓库尚无全量调度、失败隔离和新入口。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py tests/integration/pipeline/test_import_todo_corpus_cli.py -q
```

**预期输出：** FAIL，原因是 `run_todo_batch` 或脚本不存在。

**Step 3: Write the minimal coordinator**

`run_todo_batch` 按冻结清单循环：转 `processing` 并保存 → 分类/提取/边界/解析/切块/门禁 → 阻断项留状态后继续 → 合格项转 `committing` 并串行单文件 commit → 成功或当前文件失败 → 汇总批次且不批次回滚。

依赖以协议或可调用对象注入，单元测试使用 fake，但不得在生产默认值中用 fake OCR。每个文件使用独立 attempt、run_id 和 staging。

**Step 4: Write the minimal CLI**

`scripts/import_todo_corpus.py` 使用 `argparse`，支持：

- `--source-root`，默认 `法律文本/todo`；
- `--data-dir`，默认读取 `Settings`；
- `--batch-id`，省略时生成；
- `--dry-run`；
- `--verify-source-only`；
- 可选的结构化人工复核记录输入。

退出码：正常模式全部提交、或 dry-run 全部通过为 `0`；存在待复核/失败为 `2`；批次基础设施失败或源摘要不一致为 `1`。输出只打印批次 ID、计数和报告路径，不打印附件或模板正文。

**Step 5: Run unit and integration tests**

**命令执行意图：** 验证批次失败隔离、串行 commit 和 CLI 参数契约。

```bash
conda run -n fire python -m pytest tests/unit/services/test_legal_ingestion_batch.py tests/integration/pipeline/test_todo_corpus_batch.py tests/integration/pipeline/test_import_todo_corpus_cli.py -q
```

**预期输出：** PASS，单份失败不污染其他正式结果，CLI 不移动源文件。

**Step 6: Verify the real source snapshot**

先只验证真实 14 文件摘要；再用 `--dry-run` 执行当前已具备依赖的提取和门禁。OCR 未批准时，两份 PS 必须明确为待复核或依赖阻塞，不能伪造成功。

**命令执行意图：** 验证真实清单完整且源文件只读。

```bash
conda run -n fire python scripts/import_todo_corpus.py --verify-source-only
```

**预期输出：** 发现并验证 14 份文件，摘要一致，退出码 `0`。

**命令执行意图：** 验证批次协调、报告和异常隔离，不写正式产物。

```bash
conda run -n fire python scripts/import_todo_corpus.py --dry-run
```

**预期输出：** 生成完整批次报告；所有文件有终止状态；未批准 OCR 时退出码 `2`，且正式 `data/normalized`、`data/structured`、`data/chunks`、索引和增量 manifest 不变。

**Step 7: Run the full phase regression**

**命令执行意图：** 验证分卷三与现有离线链路、append-only 回归兼容。

```bash
conda run -n fire python -m pytest tests/unit/services tests/integration/pipeline/test_incremental_import_pipeline.py -q
```

**预期输出：** 全部相关测试通过；真实扫描件未被 fake 覆盖。

**Step 8: Record the checkpoint**

**Checkpoint：** 批次全量发现、逐文件串行 commit、无全局事务；阻断文件无正式产物；单份失败不影响他项；manifest 仅记 committed；源文件不移动；OCR 未批准时不宣称全量完成。
