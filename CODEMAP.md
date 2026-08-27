---
mode: learning
ignore: 默认规则 + .gitignore（排除 __pycache__/.pytest_cache/.deepeval/.humanize/egg-info、var/、data/ 生成物子目录、法律文本/；统计口径已排除 .pdf/.db/.jsonl 等二进制）
generated_at: 2026-08-27
stats:
  total_files: 248
  total_lines: 54230
  total_size: 2.0 MB
---

# fire-law-rag CODEMAP

## Summary

本机单用户的消防法规 RAG 问答系统：离线管线把原始法规文本建为关键词+向量双索引，FastAPI 后端提供证据绑定的问答与会话管理，含按时间线归档的设计文档库。

## Task Guide

| 任务 | Domain | Target | Also Check |
|---|---|---|---|
| 理解一次问答请求从 API 到证据检索与答案生成的完整链路 | 后端服务 | `app/CODEMAP.md`（问答链路行）+ `app/api/chat.py` | `app/services/retriever.py` |
| 理解多轮会话管理与流式事件输出机制 | 后端服务 | `app/CODEMAP.md`（会话管理行）+ `app/services/conversation_turn_service.py` | `tests/integration/api/test_conversations_api.py` |
| 理解离线索引构建（语料→结构化→切块→双索引）全流程 | 建库脚本 | `scripts/CODEMAP.md` + `scripts/build_corpus.py` + `scripts/build_index.py` | `tests/integration/pipeline/test_build_pipeline.py` |
| 理解增量导入的 staging 校验、提交与失败回滚机制 | 摄取管线 | `scripts/import_new_corpus.py` + `app/services/incremental_import.py` | `tests/integration/pipeline/test_ws3_qualified_incremental_import.py` |
| 理解 W/S1/S2/S3 边界判定与质量门禁判定矩阵 | 摄取管线 | `app/services/legal_quality_gates.py.analysis.md` + `app/services/legal_ingestion_orchestrator.py` | `app/services/CODEMAP.md` 边界判定各域 |
| 理解新评测系统（evaluation-only）四卷结构与设计权威口径 | 架构设计文档 | `docs/CODEMAP.md` + `docs/architecture_or_strategy/2026-07-23-evaluation-optimization-loop-architecture-design.md` | 根目录 `新评测系统设计总卷.md`（已被 AGENTS.md 标注过时，注意甄别） |
| 查找 Golden Set 与 Adversarial Case 生成素材及流程 | 评测素材 | `eval_set/CODEMAP.md` + `eval_set/Adversarial_Case生成流程.md` | `eval_set/RAG_Golden_Set.json` |
| 了解测试分层与某生产模块如何被验证 | 测试层 | `tests/CODEMAP.md` Task Guide | 对应生产模块的 CODEMAP 行 |
| 理解配置加载与环境变量入口 | 配置中心 | `app/core/settings.py` + `.env.example` | — |

## Subdirectories

| Dir | Domain | Depends On | Purpose |
|---|---|---|---|
| `app/` | 后端服务 | data/ 运行时产物、外部 LLM/嵌入模型 | FastAPI 后端：会话管理、双路证据检索、法条绑定生成、摄取质量门禁管线与 Web UI |
| `scripts/` | 建库脚本 | app.core, app.services | CLI 入口层：离线建库、增量导入 |
| `tests/` | 测试层 | app, scripts（被测目标）、fixtures | unit/integration 两层测试 + 各阶段最小样本 fixtures |
| `docs/` | 架构设计文档 | — | 设计/实施/参考三类 markdown 文档的时间线归档（59 篇） |
| `eval_set/` | 评测素材 | — | Golden Set 正例 QA 与 Adversarial Case / Edge Case 生成素材（部分为 Draft/Under Review） |
| `data/` | 构建产物存储 | 由 scripts 写入 | 大部分为 gitignored 可重建产物 |
| `法律文本/`（gitignored）/ `新法规文件/` | 原始语料素材（非代码，PDF/docx） | 被 corpus_ingestor/incremental import 消费 | 原始法规文件；不在源码统计与子级 CODEMAP 覆盖范围内 |
| `var/`（gitignored） | 本机运行时数据 | app/main、评测脚本写入 | conversations.db 会话库与评测调试临时产物 |

## Key Exports

| Symbol | Source | Line |
|---|---|---|
| create_app / app (FastAPI instance) | app/main.py | L:38 / L:71 |
| get_settings / Settings | app/core/settings.py | L:44 / L:8 |
| run_incremental_import / IncrementalImportError | app/services/incremental_import.py | L:122 / L:29 |
| run_legal_ingestion | app/services/legal_ingestion_orchestrator.py | L:305 |
| Retriever | app/services/retriever.py | L:17 |
| build_answer / build_citation_label | app/services/answer_service.py | L:21 / L:56 |
| SentenceTransformerEmbedder | app/services/embedder.py | L:46 |
| OpenAIChatClient | app/services/chat_client.py | L:23 |
| build_chunks / write_chunks | app/services/chunk_builder.py | L:16 / L:151 |
| parse_legal_document / parse_legal_intermediate | app/services/structure_parser.py | 顶层 |
| ChatRequest / EvidenceItem | app/schemas/chat.py | L:19 / L:4 |
| ConversationStreamEvent | app/schemas/conversation.py | L:72 |

## Files

| File | Domain | Function |
|---|---|---|
| README.md | 项目入口 | 系统简介、技术栈、架构图、增量导入与评测命令用法 |
| AGENTS.md | 代理导航 | 当前目标/强制规则；文末附 CODEMAP Navigation Protocol 导航协议块 |
| pyproject.toml | 包配置 | fire-law-rag 依赖声明、pytest testpaths 配置 |
| .env.example | 配置模板 | CHAT_*、EMBEDDING_MODEL_NAME、WS_RAG_* 等环境变量样例 |
| 新评测系统设计总卷.md | 架构设计文档 | 新评测系统 evaluation-only 总卷——**已过时**，设计权威口径见 docs/architecture_or_strategy/ 三份分卷 |
| 评测维度.md | 架构设计文档 | 评测维度备忘 |
