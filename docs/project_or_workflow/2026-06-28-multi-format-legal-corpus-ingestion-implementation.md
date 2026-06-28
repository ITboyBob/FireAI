# 多格式法律语料摄取 Implementation Plan

> This plan is intended for direct batch execution in the current workspace.

**Goal:** 为 `法律文本/todo/` 的 14 份真实法规建立多格式分类、提取、正文边界、质量门禁、批次状态与逐文件 append-only 提交能力。

**Architecture:** 在现有单文件 append-only 提交机制上游增加批次清单、双轴分类、提取器路由、统一中间格式和质量门禁。批次层只负责发现、调度与审计，正式写入继续复用现有逐文件 staging、preflight、索引追加、回滚和 manifest。

**Tech Stack:** Python 3.14、标准库、现有 FastAPI/Pydantic/SQLite/FAISS 代码、macOS `textutil`、现有 PDF 命令行能力、待批准的中文 OCR 适配器、pytest；所有代码和测试必须使用 conda 环境 `fire`。

---

## 1. 执行前提

本计划依据以下已批准设计：

- [多格式法律语料摄取总设计](../architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)
- [文件分类与提取器路由设计](../architecture_or_strategy/2026-06-28-legal-source-classification-and-extraction-design.md)
- [目标正文边界与统一中间格式设计](../architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md)
- [质量门禁与批次状态设计](../architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md)
- [todo 法律语料评估基线](../reference_material/2026-06-28-todo-legal-corpus-assessment.md)

现有 append-only 行为以[增量导入实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)及当前代码为准。

## 2. 全局硬门禁

1. 每个 Phase 开始前重新列出已确认输入、缺失输入和默认值。
2. 所有代码、脚本和测试命令使用 `conda run -n fire ...`。
3. 任何依赖安装前必须向用户列出依赖、用途、版本、安装位置和包管理工具。
4. OCR 引擎和中文语言资源未获批准前，只能实现协议、fake 和依赖门禁，不得安装或伪造真实验证。
5. 新增或修改测试必须先运行红测，再写最小实现，再运行绿测。
6. 离线链路测试通过后，必须基于 `法律文本/todo/` 当前真实文件补做验证。
7. 真实 14 文件测试不得使用 `skip`、`xfail` 或“缺失则返回”。
8. 原始 `法律文本/` 只读；解析和提交过程不得移动 `todo/` 或 `done/`。
9. 附件、评分表和文书模板正文不得写入 normalized、structured、chunks、报告或日志。
10. 单份文件未通过质量门禁时，不得调用正式 commit。
11. 不建立 14 文件全局事务；正式 commit 串行并保持逐文件回滚。
12. 每份实施计划分卷和新增文档不得超过 500 行。

## 3. 包管理工具

| 环境 | 包管理工具 | 当前结论 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；如批准 Python 包，使用该环境内明确选定的 conda 或 pip | 当前不安装 |
| OCR/命令行工具 | 必须选择可安装并运行于 conda `fire` 的方案 | 选型和安装待批准 |
| 前端 | 不涉及 | 不安装 |
| 其他运行环境 | 不涉及 | 不安装 |

若候选 OCR 方案只能通过 Homebrew 或系统级安装，必须停止并请求用户决定是否修改仓库的 conda-only 规则。

## 4. 分卷导航

- [分卷一：输入清单、领域模型与双轴分类](./2026-06-28-multi-format-legal-corpus-ingestion-implementation-part-1.md)
- [分卷二：提取器、正文边界与统一中间格式](./2026-06-28-multi-format-legal-corpus-ingestion-implementation-part-2.md)
- [分卷三：质量门禁、批次状态与 append-only 集成](./2026-06-28-multi-format-legal-corpus-ingestion-implementation-part-3.md)
- [分卷四：真实全量验收、文档同步与最终审计](./2026-06-28-multi-format-legal-corpus-ingestion-implementation-part-4.md)

## 5. 执行顺序

1. 先执行分卷一，冻结输入契约和分类证据。
2. 依赖审计获得用户批准后，执行分卷二的真实 PDF/OCR 适配；未获批准时只完成不依赖真实 OCR 的协议任务。
3. 执行分卷三，只有质量资格可以进入现有单文件 commit。
4. 最后执行分卷四，以全部 14 份真实文件完成验收。

不得跳过前一分卷的完成检查点直接实现后续正式提交。

## 6. Git 策略

- 本计划授权执行阶段在每个完整 Phase 通过对应测试与真实验证后执行一次 `git add` 和 `git commit`。
- commit 说明必须使用中文，并只包含当前 Phase 已验证的改动。
- 工作区存在非代理产生的改动时必须避开；无法安全避开则停止提交并报告。
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写操作。
- 当前文档创建任务不执行 commit。

## 7. 分卷完成定义

### 分卷一

- 14 文件冻结清单稳定；
- 文件真实类型和分类证据可机器读取；
- W/PT/PS/PX 与 S1—S4 候选分类有测试固定；
- 没有修改正式 `data/`。

### 分卷二

- 三类提取器遵守共同协议；
- 目标正文可以形成合法 `LegalDocumentIntermediate`；
- 排除内容不被持久化；
- OCR 未批准时相关真实任务明确停止，不伪造通过。

### 分卷三

- 门禁和状态转换被测试固定；
- 批次失败隔离和逐文件 commit 被证明；
- 未通过文件不能产生正式产物；
- 现有 append-only 回滚能力未被破坏。

### 分卷四

- 真实清单正好覆盖 14 文件；
- 每份文件均有完整状态、门禁和审计证据；
- 全部文件达到 `committed`；
- 源文件摘要不变；
- 文档、索引和读取规则与实现同步。

## 8. 总体验收命令

**命令执行意图：** 验证多格式摄取相关单元、集成与真实语料测试。

```bash
conda run -n fire python -m pytest tests/unit/services tests/integration/pipeline -q
```

**预期输出：** 所有相关测试通过，真实 14 文件测试没有 `skipped` 或 `xfailed`。

**命令执行意图：** 验证仓库完整测试集。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部测试通过；若存在已登记的历史例外，必须在执行记录中逐项说明，不能把新功能失败归入历史例外。
