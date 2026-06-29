# 多格式法律语料摄取实施计划（分卷四）

> **状态：已被替代。** 当前任务必须从[法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)进入对应里程碑计划；本文仅用于历史追溯。

> 本分卷负责真实全量验收、文档同步和最终审计；入口见[实施计划总览](./2026-06-28-multi-format-legal-corpus-ingestion-implementation.md)。

## 阶段输入检查

**已确认：**

- 分卷一至三的完成检查点已经通过；
- OCR 与 PDF 真实提取依赖已经用户批准并安装到 conda `fire`，或仓库已有等效能力；
- 14 份冻结清单与评估基线一致；
- 每份文件拥有独立 attempt、质量报告和提交资格。

**缺失项：**

- 任一前置检查点缺失时不得开始本分卷；
- 任一 OCR 依赖未经批准时不得声称扫描型 PDF 已完成。

**默认值：**

- 无默认绕过；
- 真实文件缺失、路径变化或摘要变化均作为失败。

**依赖情况：** 本分卷无需新增依赖，沿用前序已批准并安装到 conda `fire` 的环境。后端包管理工具不再发生操作；前端和其他运行环境不涉及。

## Task 15：建立真实 14 文件验收清单测试

**Files:**

- Create: `tests/integration/pipeline/test_todo_legal_corpus_inventory.py`
- Read: `docs/reference_material/2026-06-28-todo-legal-corpus-assessment.md`

**Step 1: Write the failing test**

建立固定的 14 个相对路径清单，断言：

- `法律文本/todo/` 递归发现结果与清单完全一致；
- 没有遗漏、额外业务文件或重复相对路径；
- 每个文件都能读取并计算 SHA-256；
- `.DS_Store` 不进入业务清单。

**Step 2: Run test to verify it fails**

**命令执行意图：** 证明当前仓库尚无冻结清单契约。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_corpus_inventory.py -q
```

**预期输出：** FAIL，原因是清单发现器或固定基线尚未接线。

**Step 3: Write minimal implementation**

复用分卷一实现的清单器，测试中不复制发现逻辑。文件缺失必须列出相对路径并失败，不得 `skip`。

**Step 4: Run test to verify it passes**

重复上一步命令。

**预期输出：** PASS，测试收集并验证恰好 14 份业务文件。

**Step 5: Record the completion checkpoint**

Expected state:

- 真实文件集合被测试固定；
- 后续测试可以参数化遍历同一冻结清单；
- 源文件未被修改。

## Task 16：建立逐文件真实质量验收矩阵

**Files:**

- Create: `tests/integration/pipeline/test_todo_legal_corpus_quality.py`
- Modify: `tests/integration/pipeline/test_incremental_import_real_smoke.py`
- Read: `docs/architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md`

**Step 1: Write the failing tests**

使用冻结清单参数化 14 份文件，并按评估基线固定至少以下断言：

- Word 文件无 `PAGE \* MERGEFORMAT`、HYPERLINK 指令和印发尾注污染；
- 文本型 PDF 正文页覆盖率为 100%，40 条顺序完整；
- 两份扫描型 PDF 正文页均完成 OCR，关键条号通过置信度门禁；
- 安全生产衔接办法的第三十二、三十三条不重复；
- 河北省消防设施管理规定的前置“附件2”不误删目标正文；
- 执法过错责任追究规定的文书模板不进入正文；
- 每份文件的 structured 条文与 chunks 覆盖一致；
- 所有失败场景返回稳定中文错误，不产生正式产物。

删除旧 smoke 中“路径不存在则 skip”的逻辑。真实文件缺失必须失败并列出路径。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明现有真实 smoke 不能覆盖当前 `todo`。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_corpus_quality.py tests/integration/pipeline/test_incremental_import_real_smoke.py -q
```

**预期输出：** FAIL，且不得显示因真实文件缺失而 `skipped`。

**Step 3: Write minimal implementation**

只修复被真实矩阵证明的问题：

- 调整清洗、边界或门禁规则；
- 不为单一文件硬编码完整正文；
- 合法例外必须记录来源证据；
- 扫描 OCR 不达标时保留待复核状态，不伪造成功。

每轮只处理一个失败类别，并回到对应单元测试执行红绿循环。

**Step 4: Run tests to verify they pass**

重复上一步命令。

**预期输出：** 14 份文件全部完成质量判定；没有 `skip` 或 `xfail`。

**Step 5: Record the completion checkpoint**

Expected state:

- 当前已知的格式、断行、页码域、重复条文和附件污染都被真实测试覆盖；
- 所有源文件摘要与测试前一致；
- 真实验收结果可以回溯到质量报告。

## Task 17：真实逐文件提交与检索一致性验证

**Files:**

- Create: `tests/integration/pipeline/test_todo_legal_corpus_commit.py`
- Modify: `tests/integration/pipeline/test_incremental_import_pipeline.py`
- Modify: `tests/unit/services/test_retriever.py`

**Step 1: Write the failing tests**

在临时 `data_dir` 中从已知旧语料建立基线索引，然后依次提交通过门禁的 14 份文件，断言：

- 每份文件使用独立 staging 和 run 标识；
- commit 顺序执行，失败不会破坏先前已提交文件；
- normalized、structured、chunks、关键词索引、向量映射和 manifest 的 document_id 集合一致；
- 每条目标条文均能从关键词索引命中；
- 向量映射位置连续，数量与向量索引一致；
- 排除内容关键词不能命中新增 chunks；
- 重跑同一来源触发 append-only 冲突且正式产物不变。

测试使用 fake embedder，避免真实模型波动；不得 mock 掉正文边界、质量门禁或正式提交路径。

**Step 2: Run tests to verify they fail**

**命令执行意图：** 证明批次结果尚未与真实 append-only 提交闭环。

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_todo_legal_corpus_commit.py -q
```

**预期输出：** FAIL，原因是全量提交编排或一致性检查尚未完成。

**Step 3: Write minimal implementation**

修复真实提交暴露的问题，但保持：

- 单文件 commit API；
- 正式索引修改串行化；
- manifest 最后写入；
- 单份失败只回滚自己的提交；
- 源文件目录只读。

**Step 4: Run tests to verify they pass**

重复上一步命令。

**预期输出：** PASS，14 份文件在临时正式产物中全部提交并可检索。

**Step 5: Record the completion checkpoint**

Expected state:

- 全量处理目标被正式产物和检索证据证明；
- append-only 冲突、回滚和索引一致性未退化；
- 排除内容未进入索引。

## Task 18：同步权威文档与完成最终审计

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture_or_strategy/工程技术标准.md`
- Modify: `docs/system_meta/文档索引.md`
- Modify: `docs/system_meta/文档读取规则.md`
- Modify: `docs/reference_material/2026-06-28-todo-legal-corpus-assessment.md`

**Step 1: Write the failing documentation checks**

为文档一致性增加轻量检查，至少验证：

- 文档索引登记所有 Markdown；
- 所有登记路径存在；
- 所有相对 Markdown 链接有效；
- `docs/` 下每份 Markdown 不超过 500 行；
- README 指向当前多格式入口；
- 工程技术标准记录已实现能力，而不是仍写成未来设计；
- 评估基线逐文件状态与最终真实结果一致。

文档检查脚本若需要新增，使用 `scripts/validate_docs.py`，不得引入新依赖。

**Step 2: Run checks to verify they fail**

**命令执行意图：** 找出实现完成后尚未同步的权威文档。

```bash
conda run -n fire python scripts/validate_docs.py
```

**预期输出：** FAIL，并列出缺失登记、断链、超长或状态不一致项。

**Step 3: Update documentation**

只把已经由代码和真实测试证明的行为写入工程技术标准：

- 支持的来源类型；
- 分类、边界和质量门禁；
- 批次与逐文件提交语义；
- OCR 真实依赖和运行命令；
- 附件排除与源文件只读规则；
- 真实验收命令。

评估基线保留原始问题证据，并增加最终处理状态；不要删除失败历史。

**Step 4: Run documentation checks**

重复上一步命令。

**预期输出：** PASS，无未登记 Markdown、断链或超过 500 行的文件。

**Step 5: Run final verification**

**命令执行意图：** 验证离线链路、在线回归和全部文档状态。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部测试通过；真实 14 文件相关测试没有 `skipped` 或 `xfailed`。

**Step 6: Verify source immutability**

**命令执行意图：** 对比冻结清单中的测试前后 SHA-256。

```bash
conda run -n fire python scripts/import_todo_corpus.py --verify-source-only
```

**预期输出：** 14 份文件摘要全部一致，`todo/` 与 `done/` 没有被移动或改写。

**Step 7: Record the completion checkpoint**

Expected state:

- 14 份真实文件全部为 `committed`；
- 正式语料、索引、manifest 和批次报告一致；
- 所有权威文档与实现同步；
- 每份 Markdown 少于 500 行；
- 未执行 push 或历史改写操作。
