---
mode: learning
generated_at: 2026-08-27
---

# scripts/CODEMAP

## Summary

命令行入口层：离线语料构建与索引建库、增量导入新法规。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解离线全量语料构建入口（发现→归一化→结构→分块） | 语料构建入口 | build_corpus.py | app/services/{corpus_ingestor, normalizer, structure_parser, chunk_builder}.py |
| 理解关键词+向量双索引建库入口 | 索引建库入口 | build_index.py | app/services/{keyword_index, vector_index, embedder}.py |
| 理解增量导入 CLI 的批次报告与退出码约定 | 增量导入入口 | import_new_corpus.py | app/services/incremental_import.py |

## Key Exports

| Symbol | Source | Line |
| --- | --- | --- |
| main (语料构建 CLI) | build_corpus.py | L:16 |
| main (双索引建库 CLI) | build_index.py | L:58 |
| main (增量导入 CLI) | import_new_corpus.py | L:129 |

## Files

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| build_corpus.py | 语料构建入口 | ← external/app.services；→ data/{normalized,structured,chunks} | 把 PROJECT_ROOT 插入 sys.path 后调用 Settings：discover_documents → normalize_document → parse_legal_document → build_chunks/write_chunks，完成 data 目录四类产物 |
| build_index.py | 索引建库入口 | ← app.services；→ data/index + data/retrieval.db | load_chunks 读取 chunks 目录 JSON → SentenceTransformerEmbedder → build_keyword_index + build_vector_index 建双路索引 |
| import_new_corpus.py | 增量导入入口 | ← app.core.settings, app.services({corpus_ingestor, embedder, incremental_import, legal_ingestion_batch})；→ var 批次报告 | 解析 --source/--manifest 来源并计算 sha256 → run_incremental_import 在 staging 内重建产物并提交 → 写 BatchFileResult 批次报告 → 按结果决定退出码；支持单文件与批次两种摘要输出 |

## File Dependencies

| File | Imports (in-dir) | Exposed To (in-dir) |
| --- | --- | --- |
| build_corpus.py / build_index.py / import_new_corpus.py | （互不依赖） | （互不依赖） |
