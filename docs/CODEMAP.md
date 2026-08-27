---
mode: learning
generated_at: 2026-08-27
---

# docs/CODEMAP.md

## Summary

`docs/` 是按时间线归档的设计、实施与参考文档库：法规摄取架构与 W-S RAG/新评测系统等设计文档（architecture_or_strategy）、逐里程碑的 TDD 实施计划记录（project_or_workflow）、以及历史设计与运行时契约核验资料（reference_material）。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解消防问答系统 2.0 的产品定位与能力边界 | 产品需求设计 | `architecture_or_strategy/2026-04-11-fire-qa-system-2.0-prd.md` | `architecture_or_strategy/工程技术标准.md` |
| 理解法规摄取总体架构与双轴策略路由决策 | 法规摄取设计系列 | `architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md` + `2026-06-29-legal-ingestion-overall-architecture.md` | 能力路线图见 `project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md` |
| 理解法规摄取质量门禁与批次状态设计 | 法规摄取设计系列 | `architecture_or_strategy/2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md` | W-S1 实施分卷三（质量资格部分） |
| 理解 S1/S2/S3 正文边界策略的演进 | 法规摄取设计系列 | `architecture_or_strategy/2026-06-28-legal-content-boundary-and-intermediate-model-design.md`、`2026-07-04-s3-trailing-exclusion-boundary-design.md` | 实施记录：W-S1/W-S2/W-S3 实施系列 |
| 理解 NDJSON 状态流问答交互设计 | 产品与技术设计 | `architecture_or_strategy/2026-04-23-fire-qa-ndjson-status-stream-design.md` | 2.0 实施计划分卷三 |
| 理解 W-S RAG 评测（evaluation-only）总体设计 | W-S RAG 评测设计 | `architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md` | Dashboard 三篇分卷；实施系列 |
| 理解新评测系统（evaluation-only）总体架构 | 新评测系统设计卷册 | 分卷一 `architecture_or_strategy/2026-07-23-evaluation-optimization-loop-architecture-design.md`（含总卷导航 `../../新评测系统设计总卷.md`） | 分卷二/三；注意 AGENTS.md 已标注总卷「过时」 |
| 查找 TDD 实施记录（按里程碑） | 项目实施记录 | 各实施系列，如 `project_or_workflow/2026-07-05-ws-rag-evaluation-implementation.md` 系列 | 对应 design 文档核验实施一致性 |
| 核验运行时依赖契约（textutil/Pydantic/pytest 等） | 参考资料·契约核验 | `reference_material/2026-06-30-s2-runtime-contract-verification.md` 等 4 篇核验记录 | 各对应实施计划 |
| 追溯一期 RAG 历史设计 | 历史参考资料 | `reference_material/2026-03-28-fire-law-rag-design.md` + 实施计划系列 | 文内已声明被 2.0 PRD 与工程技术标准取代 |

## Subdirectories

| Dir | Domain | Depends On | Purpose |
| --- | --- | --- | --- |
| `architecture_or_strategy/` | 架构设计文档 | 上位文档关系由各文「上位设计」字段自述；引用 `法律文本/todo/` 与 `data/` 结构 | 存放产品 PRD、工程技术标准、法规摄取专项设计与 ADR、W-S RAG 评测及新评测系统设计卷册（2026-04 → 2026-07/08） |
| `project_or_workflow/` | 项目实施记录 | 分别依赖 architecture_or_strategy 中对应设计文档 | 按 TDD 分批执行的各里程碑实施计划及其分卷存档（2.0 实施、增量导入、W-S1/S2/S3、W-S RAG 评测与 Dashboard） |
| `reference_material/` | 参考资料档案 | 被现行 PRD / 工程技术标准在权威性上覆盖 | 一期历史设计、标准化切块重构、todo 语料评估基线和运行时契约核验记录 |
| `repo_overview/` | （目录不存在） | — | 当前不存在该子目录，预留为空概念 |
| `system_meta/` | （目录不存在） | — | 当前不存在该子目录；《工程技术标准》中引用的 `../system_meta/文档索引.md`、`文档读取规则.md` 均缺失 |

## Files

### architecture_or_strategy（17 篇）

| File 或系列 | Domain | 内容一句话 |
| --- | --- | --- |
| `工程技术标准.md` | 工程标准 | 记录当前仍有效的环境规则、离线/在线分离、建库产物一致性与测试要求等技术标准。 |
| `2026-04-11-fire-qa-system-2.0-prd.md` | 产品需求 | 消防问答系统 2.0 的唯一产品标准 PRD，定义定位、能力边界与验收口径。 |
| `2026-04-23-fire-qa-ndjson-status-stream-design.md` | 交互设计 | 后端 NDJSON 状态流、前端基于可信 payload 逐字呈现的问答体验设计。 |
| 法规摄取设计系列（7 篇）：`2026-06-28-multi-format-legal-corpus-ingestion-design.md`、`2026-06-28-legal-source-classification-and-extraction-design.md`、`2026-06-28-legal-content-boundary-and-intermediate-model-design.md`、`2026-06-28-legal-ingestion-quality-gates-and-batch-state-design.md`、`2026-06-29-unified-legal-ingestion-entry-adr.md`、`2026-06-29-legal-ingestion-overall-architecture.md`、`2026-07-04-s3-trailing-exclusion-boundary-design.md` | 法规摄取设计 | 总体架构 + ADR + 多格式摄取总设计与分类提取、正文边界、质量门禁三份专项分卷及 S3 尾部排除细化设计。 |
| W-S RAG 评测设计系列（4 篇）：`2026-07-04-ws-rag-evaluation-design.md`、`2026-07-05-ws-rag-evaluation-dashboard-design.md`、`2026-07-05-ws-rag-evaluation-dashboard-data-contract.md`、`2026-07-05-ws-rag-evaluation-dashboard-interface-and-validation.md` | W-S RAG 评测设计 | 单文件 RAG 问答评测总设计及其 Streamlit Dashboard 的总览、数据契约和界面验证三分卷。 |
| 新评测系统设计卷册（3 篇）：`2026-07-23-evaluation-optimization-loop-architecture-design.md`（分卷一）、`2026-07-27-ragas-val-set-query-generation-design.md`（分卷二）、`2026-07-27-ragas-response-reference-rubric-judge-design.md`（分卷三） | 新评测系统设计 | evaluation-only 新评测系统的评测执行与报告架构、Ragas val_set 生成冻结、八项 Metric 与评分契约三分卷；总卷位于仓库根 `新评测系统设计总卷.md`（AGENTS.md 标注过时）。 |

### project_or_workflow（30 篇）

| File 或系列 | Domain | 内容一句话 |
| --- | --- | --- |
| 消防问答系统 2.0 实施计划系列（总览 + 3 分卷，共 4 篇，前缀 `2026-04-11-fire-qa-system-2.0-implementation*`） | 项目实施记录 | 会话持久化、响应模型、编排到 NDJSON 状态流专项的 2.0 升级 TDD 实施计划。 |
| Append-Only 增量导入实施计划系列（总览 + 4 分卷，共 5 篇，前缀 `2026-04-29-append-only-incremental-corpus-import*`） | 项目实施记录 | 显式新法规 staging → 两阶段 preflight 提交 → 失败回滚的全链路局部增量导入实施。 |
| `2026-06-29-legal-ingestion-capability-roadmap.md` | 项目实施记录 | 法规摄取工作的总体规划入口，规定何时必须同步更新路线图。 |
| W-S1 端到端摄取实施计划系列（总览 + 4 分卷，共 5 篇，前缀 `2026-06-29-w-s1-end-to-end-ingestion-implementation*`） | 项目实施记录 | 冻结 W-S1 视图、建立双轴策略协议与统一编排器并完成 8 份 Word 法规的端到端摄取验收。 |
| S2 边界能力与 W-S2 组合验收实施计划系列（总览 + 3 分卷，共 4 篇，前缀 `2026-06-30-s2-boundary-and-w-s2-acceptance-implementation*`） | 项目实施记录 | 实现复合发布材料前置排除的 S2 边界策略并让 2 份 W-S2 法规通过质量资格正式入库。 |
| S3 边界能力与 W-S3 组合验收实施计划系列（总览 + 2 分卷，共 3 篇，前缀 `2026-07-04-s3-boundary-and-w-s3-acceptance-implementation*`） | 项目实施记录 | 已完成的 S3 正文后排除（尾部附件/评分表/文书模板）策略实施与唯一 W-S3 文件正式导入审计记录。 |
| W-S RAG 评测实施计划系列（总览 + 3 分卷，共 4 篇，前缀 `2026-07-05-ws-rag-evaluation-implementation*`） | 项目实施记录 | 共享契约、不可变 dataset 生成、真实 RAG+Judge 执行、基线登记与 run 目录原子发布的评测链路实施。 |
| W-S RAG 评测 Dashboard 实施计划系列（总览 + 3 分卷，共 4 篇，前缀 `2026-07-05-ws-rag-evaluation-dashboard-implementation*`） | 项目实施记录 | 共享 loader、Streamlit 单页四视图与 mock MVP 浏览器验证的只读 Dashboard 实施。 |

### reference_material（12 篇）

| File 或系列 | Domain | 内容一句话 |
| --- | --- | --- |
| 一期 RAG 设计与实施系列（4 篇）：`2026-03-28-fire-law-rag-design.md`、`2026-03-28-fire-law-rag-implementation.md`、`2026-03-28-fire-law-rag-implementation-part-1.md`、`2026-03-28-fire-law-rag-implementation-part-2.md` | 历史参考资料 | 一期纯本机消防法律 RAG 的历史设计与两分卷实施计划，已被 2.0 PRD 与工程技术标准在权威性上取代。 |
| `2026-03-28-normalization-and-chunking-refactor-design.md` | 历史参考资料 | 修复 HYPERLINK 字段码污染与枚举条文切块过粗问题的上游重构设计。 |
| `2026-03-28-normalization-and-chunking-refactor.md` | 历史参考资料 | 上述重构设计的配套 TDD 实施计划。 |
| `2026-06-28-todo-legal-corpus-assessment.md` | 语料评估基线 | `法律文本/todo/` 全部 14 份文件的只读格式分布与可摄取性评估证据。 |
| `2026-06-29-w-s1-runtime-contract-verification.md` | 契约核验 | 核验 macOS `textutil(1)` 与 Python 3.14 subprocess 在 W-S1 链路中的行为契约。 |
| `2026-06-30-s2-runtime-contract-verification.md` | 契约核验 | 核验 Python 3.14 dataclasses、Enum、argparse 在 S2 任务中的行为契约。 |
| `2026-07-04-s3-runtime-contract-verification.md` | 契约核验 | 核验 re 模块、frozen dataclass、Enum 异常与 pytest 行为在 S3 任务中的契约。 |
| `2026-07-05-ws-rag-evaluation-runtime-contract-verification.md` | 契约核验 | 核验 Pydantic v2（fire 环境 2.12.5）模型契约在评测链路中的用法结论。 |
| `2026-07-29-evaluation-optimization-template-components.md` | 上游模板摘录 | 仅用于追溯的上游 Evaluation/Optimization 模板组件清单，不构成任何契约权威。 |

### repo_overview 与 system_meta

两个子目录当前均不存在（仅约定）；无直属文件可收录。
