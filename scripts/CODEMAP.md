---
mode: learning
generated_at: 2026-08-27
---

# scripts/CODEMAP

## Summary

命令行入口层：离线语料构建与索引建库、增量导入新法规、W/S 评测数据集生成与评测运行（eval_ws_rag 子包，深度另见其 CODEMAP）、结果校验与基线对比。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解离线全量语料构建入口（发现→归一化→结构→分块） | 语料构建入口 | build_corpus.py | app/services/{corpus_ingestor, normalizer, structure_parser, chunk_builder}.py |
| 理解关键词+向量双索引建库入口 | 索引建库入口 | build_index.py | app/services/{keyword_index, vector_index, embedder}.py |
| 理解增量导入 CLI 的批次报告与退出码约定 | 增量导入入口 | import_new_corpus.py | app/services/incremental_import.py |
| 理解评测子系统脚本级用法（生成/评测/对比/校验） | 评测入口 | generate_ws_rag_dataset.py、evaluate_ws_rag.py、compare_ws_rag_runs.py、verify_ws_rag_evaluation_run.py | eval_ws_rag/CODEMAP.md |

## Subdirectories

| Dir | Domain | Depends On | Purpose |
| --- | --- | --- | --- |
| eval_ws_rag/ | W/S 评测子系统 | app.{core,services}、本目录根脚本 | 评测编排器、RAG 运行器、LLM judge、规则/LLM 双重打分、报告模型与原子发布、数据集存储、Streamlit dashboard、基线注册与对比（24 个文件） |

## Key Exports

| Symbol | Source | Line |
| --- | --- | --- |
| main (语料构建 CLI) | build_corpus.py | L:16 |
| main (双索引建库 CLI) | build_index.py | L:58 |
| main (增量导入 CLI) | import_new_corpus.py | L:129 |
| main (评测驱动 CLI) | evaluate_ws_rag.py | L:21 |
| main (数据集生成 CLI) | generate_ws_rag_dataset.py | L:57 |
| verify_run | verify_ws_rag_evaluation_run.py | L:64 |
| compare_runs (re-export 调用) | compare_ws_rag_runs.py | — |

## Files

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| build_corpus.py | 语料构建入口 | ← external/app.services；→ data/{normalized,structured,chunks} | 把 PROJECT_ROOT 插入 sys.path 后调用 Settings：discover_documents → normalize_document → parse_legal_document → build_chunks/write_chunks，完成 data 目录四类产物 |
| build_index.py | 索引建库入口 | ← app.services；→ data/index + data/retrieval.db | load_chunks 读取 chunks 目录 JSON → SentenceTransformerEmbedder → build_keyword_index + build_vector_index 建双路索引 |
| import_new_corpus.py | 增量导入入口 | ← app.core.settings, app.services({corpus_ingestor, embedder, incremental_import, legal_ingestion_batch})；→ var 批次报告 | 解析 --source/--manifest 来源并计算 sha256 → run_incremental_import 在 staging 内重建产物并提交 → 写 BatchFileResult 批次报告 → 按结果决定退出码；支持单文件与批次两种摘要输出 |
| generate_ws_rag_dataset.py | 评测入口 | ← scripts.eval_ws_rag({dataset_models, dataset_store, document_loader, question_generator})；→ data/eval 数据集 | 从 data/chunks 加载文档，用 LLM question_generator 按每文档题量配比生成评测问题集，原子落盘数据集（含 fingerprint） |
| evaluate_ws_rag.py | 评测入口 | ← scripts.eval_ws_rag.orchestrator({load_config, run_evaluation, write_debug_bundle}), runtime_config；→ reports 运行目录 | 加载 runtime 配置（config 文件 + 环境变量），执行完整评测 run：preflight→逐题 RAG→judge→规则校验→聚合→发布报告；致命错误写 debug bundle |
| compare_ws_rag_runs.py | 评测入口 | ← scripts.eval_ws_rag.baseline | 注册基线或把指定 run 与基线做指标 diff 输出 |
| verify_ws_rag_evaluation_run.py | 评测入口 | ← scripts.eval_ws_rag({dataset_models, dataset_store, report_models}) | load_run 校验报告 schema 与文件指纹（chunk source_sha256 一致性）；verify_run 核对题目集合、指纹与分数可复现性，供 CI/审计使用 |

## File Dependencies

| File | Imports (in-dir) | Exposed To (in-dir) |
| --- | --- | --- |
| generate_ws_rag_dataset.py / evaluate_ws_rag.py / compare_ws_rag_runs.py / verify_ws_rag_evaluation_run.py | scripts.eval_ws_rag.* | （互不依赖） |
