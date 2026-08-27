---
mode: learning
generated_at: 2026-08-27
---

# app/services/CODEMAP

## Summary

后端全部领域逻辑：会话存储与多轮管理、查询规范化、关键词+向量双路检索融合、证据绑定答案生成，以及离线语料构建基础件与法规摄取（W/S1/S2/S3 边界判定、质量门禁、staging 提交）管线。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解问答主链路中检索如何归一化查询并融合双路结果 | 检索融合 | retriever.py | query_normalizer.py |
| 理解 FAISS 向量索引的构建/追加与 vector_map 校验 | 向量索引 | vector_index.py | embedder.py、vector_store.py |
| 理解 SQLite FTS 关键词索引的构建与检索 | 关键词索引 | keyword_index.py | — |
| 理解 sentence-transformers 嵌入封装与归一化 | 嵌入模型 | embedder.py | vector_store.py |
| 理解 LLM 调用容错与引文校验后的拒答策略 | 答案生成 | answer_service.py | chat_client.py |
| 理解多轮对话的状态机式流式事件编排 | 会话流转 | conversation_turn_service.py | context_manager.py、turn_classifier.py |
| 理解会话 SQLite 持久化（轮次/快照/软删除/自动标题） | 会话存储 | conversation_repository.py | conversation_service.py、conversation_presenter.py |
| 理解语料从原文到 chunk 的四步构建 | 语料构建 | corpus_ingestor.py → normalizer.py → structure_parser.py → chunk_builder.py | — |
| 理解增量导入的 staging 生成、append-only 预检与提交回滚 | 增量导入 | incremental_import.py | incremental_manifest.py |
| 理解 W 文件冻结清单与批次输入摘要 | 摄取输入盘点 | legal_ingestion_inventory.py | legal_ingestion_models.py |
| 理解 textutil 提取 Word 正文及来源分类路由 | 源提取分类 | legal_word_extractor.py + legal_source_classifier.py + legal_textutil.py | legal_ingestion_orchestrator.py |
| 理解提取协议与通用条文切分单元 | 提取协议 | legal_extractor.py + legal_boundary_common.py | legal_intermediate.py |
| 理解 S1 边界判定策略 | S1 边界 | legal_content_boundary.py | legal_boundary_common.py |
| 理解 S2 边界判定（前导材料剥离） | S2 边界 | legal_s2_boundary.py | 同上 |
| 理解 S3 边界判定（尾部印发达排除） | S3 边界 | legal_s3_boundary.py | 同上 |
| 理解提取/边界策略注册表与能力状态降级 | 策略注册 | legal_strategy_registry.py | legal_content_boundary.py |
| 理解中间表示 LegalDocumentIntermediate 与结构化解析输出 | 中间表示 | legal_intermediate.py + structure_parser.py | chunk_builder.py |
| 理解批处理文件状态机与质量报告写入 | 批处理状态机 | legal_ingestion_batch.py | legal_quality_gates.py → see legal_quality_gates.py.analysis.md |
| 理解端到端摄取编排（prepare→gate→commit） | 摄取管线 | legal_ingestion_orchestrator.py | legal_qualified_import.py |

## Key Exports

| Symbol | Source | Line |
| --- | --- | --- |
| run_legal_ingestion | legal_ingestion_orchestrator.py | L:305 |
| LegalIngestionOrchestrator | legal_ingestion_orchestrator.py | L:89 |
| run_incremental_import | incremental_import.py | L:122 |
| commit_staged_import | incremental_import.py | L:227 |
| evaluate_legal_quality | legal_quality_gates.py | L:97 |
| Retriever | retriever.py | L:17 |
| SentenceTransformerEmbedder | embedder.py | L:46 |
| OpenAIChatClient | chat_client.py | L:23 |
| build_answer / is_model_failure_uncertainty | answer_service.py | L:21 / L:131 |
| ConversationRepository | conversation_repository.py | L:71 |
| ConversationTurnService | conversation_turn_service.py | L:21 |
| normalize_query | query_normalizer.py | L:51 |
| build_chunks / write_chunks | chunk_builder.py | L:16 / L:151 |
| parse_legal_document / parse_legal_intermediate | structure_parser.py | — |
| discover_documents / build_document_id | corpus_ingestor.py | L:46 / L:42 |

## Files

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| \_\_init\_\_.py | 包出口 | ← conversation_repository.py | 仅汇出 ConversationRepository |
| answer_service.py | 答案生成 | ← chat_client.py；← schemas/chat.py；→ api/chat.py, conversation_turn_service.py, scripts/eval_ws_rag/rag_runner.py | build_answer：组装系统提示词+证据上下文调用 ChatClient，验证模型引文是否落在允许的 [n] 标签内，失败/无证据/引文无效时返回中文不确定性文案；定义四类不确定文案常量 |
| chat_client.py | 答案生成 | ← schemas/chat.py；→ answer_service.py, conversation_turn_service.py, api/{chat,conversations}.py, scripts/eval_ws_rag/orchestrator.py | OpenAIChatClient：OpenAI 兼容接口封装，JSON response_format 兼容不同 provider、内容分片解析、provider 错误抽取与可重试判定；ChatCompletionError 异常类型 |
| context_manager.py | 会话流转 | → api/conversations.py | ContextManager：按 Settings.window_turns 截取近 N 轮构造检索 context_hints 的极简实现 |
| conversation_presenter.py | 会话存储 | ← schemas/conversation.py；→ api/conversations.py | ConversationPresenter：将 repository 细节序列化为 API DTO（含回答快照展开） |
| conversation_repository.py | 会话存储 | → conversation_service.py, conversation_turn_service.py, \_\_init\_\_.py, api/conversations.py | SQLite 持久化：StoredConversation/StoredMessage/StoredTurn/StoredAnswerSnapshot 数据类；会话 CRUD、自动标题、软删除、轮次与回答快照写入；ConversationNotFoundError |
| conversation_service.py | 会话存储 | ← conversation_repository.py；→ conversation_turn_service.py | 会话 CRUD 薄封装：创建「新会话」、列表、详情、重命名、软删除、首条用户消息自动标题截断 |
| conversation_summary.py | 会话流转 | → api/conversations.py | ConversationSummaryManager：超过 summary_trigger_turns 触发的历史摘要占位管理器 |
| conversation_turn_service.py | 会话流转 | ← {answer_service, chat_client, conversation_repository, conversation_service, query_normalizer}；← schemas/conversation.py；→ api/conversations.py | 多轮核心：正常化用户问题→检索→build_answer→写库，产出阶段事件流（已收到问题/正在检索/正在生成/整理法律依据），引文正则校验法条标签 |
| corpus_ingestor.py | 语料构建 | → normalizer.py, legal_content_boundary.py, legal_s2/s3_boundary.py, legal_intermediate, incremental_import.py, orchestrator, scripts/build_corpus.py, import_new_corpus.py | CorpusDocument dataclass；discover_documents 按 KNOWN_DOCUMENT_IDS 白名单扫描法律文本目录；build_document_id 由源名生成稳定 ID |
| embedder.py | 嵌入模型 | → vector_index.py, retriever.py, api/chat.py, scripts/build_index.py, import_new_corpus.py, eval_ws_rag/orchestrator.py | SentenceTransformerEmbedder：懒加载模型、单/批量编码；normalize_vector/normalize_vectors L2 归一化；MissingEmbeddingDependencyError |
| incremental_import.py | 增量导入 | ← {chunk_builder, corpus_ingestor, incremental_manifest, keyword_index, normalizer, structure_parser, vector_index}；→ legal_ingestion_orchestrator.py, legal_qualified_import.py, scripts/import_new_corpus.py | staging 目录生成新语料产物（normalized/structured/chunks/FTS/FAISS 全在 .staging 内构建）、validate_append_only_preflight 校验正式库未被污染、commit_staged_import 发布 + 备份 + 失败逐路径回滚；CommitPlan/CommittedImport/IncrementalImportSummary |
| incremental_manifest.py | 增量导入 | → incremental_import.py | data/manifests 下导入清单：版本校验、按 document_id 冲突检测、原子写入 ManifestConflictError |
| keyword_index.py | 关键词索引 | → retriever.py, incremental_import.py, scripts/build_index.py | SQLite FTS5 chunks 表：build_keyword_index 全量建库、append_keyword_index 追加（文档冲突即 KeywordIndexConflictError）、search_keyword_index BM25 检索 |
| knowledge_version.py | 会话流转 | → api/conversations.py | KnowledgeVersionResolver：对 retrieval.db/faiss.index/vector_map.json 三文件 size+mtime 摘要生成 kb:fingerprint 知识库版本号 |
| legal_boundary_common.py | 提取协议 | ← legal_extractor.py, legal_intermediate.py；→ legal_content_boundary.py, legal_s2_boundary.py, legal_s3_boundary.py | 跨边界共享：条号/标题/页字段/印发记录/抄送/办公室落款等正则族；chinese_number_to_int 条号解析；build_body_units 从文本块重建 BodyUnit 序列；find_tail_boundary |
| legal_content_boundary.py | S1 边界 | ← {corpus_ingestor, legal_boundary_common, legal_extractor, legal_ingestion_models, legal_intermediate}；→ legal_strategy_registry.py, legal_ingestion_orchestrator.py | S1BoundaryStrategy + identify_s1_target_body：定位正文目标区（跳过目录/修订记录），产出排除区间与审阅结论 |
| legal_extractor.py | 提取协议 | ← legal_ingestion_models.py；→ boundary_common/content/s2/s3, intermediate, quality_gates, strategy_registry, word_extractor, orchestrator, quality_gates.py.analysis 所述文件 | 协议层：ExtractionRequest/ExtractedBlock/ExtractedPage/ExtractionResult 数据契约、LegalExtractor 与 LegalBoundaryStrategy Protocol、validate_extraction_result 结构完整性校验、ExtractionFailure |
| legal_ingestion_batch.py | 批处理状态机 | ← legal_quality_gates.py；→ legal_ingestion_orchestrator.py, scripts/import_new_corpus.py | FileState 状态机（pending→extracted→…→committed/failed/review）与 _STATE_TRANSITIONS 合法迁移表；BatchReport/BatchFileResult/ReviewRecord、quality report 一次性写出（sha256 校验、禁写键检查）、批次报告存读 |
| legal_ingestion_inventory.py | 摄取输入盘点 | ← legal_ingestion_models.py | freeze_batch_input：发现源文件→SourceRef 冻结（sha256/大小）→批次 digest，供摄取前输入固化比对 |
| legal_ingestion_models.py | 契约模型 | → extractor/boundaries/intermediate/models 消费群（>8 files foundational; rg "legal_ingestion_models" -l） | 源引用 SourceRef、ExtractionClass/ContentClass（W/S1/S2/S3）、IngestionDisposition 等枚举与共享 dataclass |
| legal_ingestion_orchestrator.py | 摄取管线 | ← 全线：chunk_builder/corpus_ingestor/incremental_import/legal_* /structure_parser；→ scripts 及 tests 消费方 | run_legal_ingestion 端到端：能力探测→(单文件/批次) textutil 提取→来源分类路由 W/S1/S2/S3 策略→质量门禁评估→qualified commit（合法性核验后提交）；LegalIngestionOutcome/LegalIngestionOrchestrator.prepare 入口 |
| legal_intermediate.py | 中间表示 | ← legal_extractor.py, legal_ingestion_models.py；→ chunk_builder.py, structure_parser.py, boundaries, quality_gates, orchestrator | LegalDocumentIntermediate 中间文档模型：BodyUnit/SourceSpan/标题树等结构，衔接提取与结构解析/分块 |
| legal_qualified_import.py | 摄取管线 | ← incremental_import.py；→ legal_ingestion_orchestrator.py | commit_qualified_staged_import：提交前核对 staged 产物 sha256 是否与门禁报告一致（CommitQualification），不合格抛 CommitQualificationError |
| legal_quality_gates.py | 质量门禁 | ← {legal_extractor, legal_ingestion_models, legal_intermediate, structure_parser}；→ legal_ingestion_batch.py, legal_ingestion_orchestrator.py | evaluate_legal_quality：12 类门禁串联评估（身份一致性→边界确认→条文完整性→纯度→跨层一致→chunk 覆盖→S2/S3 专项），产出 QualityReport；→ see legal_quality_gates.py.analysis.md |
| legal_s2_boundary.py | S2 边界 | ← {corpus_ingestor, boundary_common, extractor, models, intermediate}；→ strategy_registry, orchestrator | S2BoundaryStrategy：识别前导材料（批复/通知等）与正文分界，隔离元数据并可溯源标记 |
| legal_s3_boundary.py | S3 边界 | 同上依赖集；→ strategy_registry, orchestrator | S3BoundaryStrategy：识别尾部印发信息/抄送/页脚等排除区，校验正文纯净度 |
| legal_source_classifier.py | 源提取分类 | ← legal_textutil.py, legal_ingestion_models.py；→ legal_ingestion_orchestrator.py | classify_source：依据 textutil 抽出的文本特征把源文件分流到 extraction class（W docx 等）对应处理器 |
| legal_strategy_registry.py | 策略注册 | ← {content_boundary, s2_boundary, extractor, models}；→ legal_ingestion_orchestrator.py | ExtractionStrategyRegistry/BoundaryStrategyRegistry 键值注册表 + CapabilityStatus 能力枚举（available/unavailable 等）；build_* 构造函数集中装配 |
| legal_textutil.py | 源提取分类 | → legal_source_classifier.py, legal_word_extractor.py | run_textutil_stdout：macOS textutil 把 doc 转 txt/html 到 stdout 的子进程封装（TextutilRunResult） |
| legal_word_extractor.py | 源提取分类 | ← {legal_textutil, models, extractor}；→ orchestrator | WordLegalExtractor 实现 LegalExtractor 协议：textutil 转 txt 后按段落/页切块为 ExtractedBlock/Page |
| normalizer.py | 语料构建 | ← corpus_ingestor.py；→ incremental_import.py, scripts/build_corpus.py | clean_text 清洗（去超链接域代码、标题空格规范等）；normalize_document 写出 data/normalized 文本产物 |
| query_normalizer.py | 检索融合 | → conversation_turn_service.py, retriever.py, scripts/eval_ws_rag/rag_runner.py | normalize_query：繁简/全半角简化、抽出法规名/条款号/地域/日期等 canonical terms 与过滤 hints（NormalizedQuery） |
| retriever.py | 检索融合 | ← {vector_store, embedder, keyword_index, query_normalizer, vector_index}；→ api/chat.py, eval_ws_rag/orchestrator.py | Retriever.retrieve：query 归一化→关键词 FTS + FAISS 双路召回→fuse_results 加权融合去重；支持 metadata 过滤与知识库缺失探测 |
| structure_parser.py | 语料构建 | ← legal_intermediate.py；→ chunk_builder.py, incremental_import.py, quality_gates, orchestrator, scripts/build_corpus.py | parse_legal_document/parse_legal_intermediate：把归一化文本或中间表示解析为 ParsedDocument（编/章/节/条层级）；write_structured_document 落盘 |
| turn_classifier.py | 会话流转 | → api/conversations.py | TurnClassifier：轻量判断用户消息类型/是否需要检索，供事件流分支使用 |
| vector_index.py | 向量索引 | ← {embedder, vector_store}；→ incremental_import.py, retriever.py, api/chat.py, scripts/build_index.py | build_vector_index 编码 chunks 建 FAISS 并写 vector_map.json；append_vector_index 追加（维度冲突即 VectorIndexConflictError）；load_vector_map/validate_vector_map |
| vector_store.py | 向量索引 | → retriever.py, vector_index.py, api/chat.py | FaissVectorStore：懒加载 faiss 依赖（MissingVectorStoreDependencyError）、add/search/save/load；VectorStore Protocol |

## File Dependencies

| File | Imports (in-dir) | Exposed To (in-dir) |
| --- | --- | --- |
| answer_service.py | chat_client | conversation_turn_service |
| chat_client.py | — | answer_service, conversation_turn_service |
| conversation_presenter.py | — | （仅被 api 层消费） |
| conversation_service.py | conversation_repository | conversation_turn_service |
| conversation_turn_service.py | answer_service, chat_client, conversation_repository, conversation_service, query_normalizer | — |
| chunk_builder.py | legal_intermediate, structure_parser | incremental_import, legal_ingestion_orchestrator |
| incremental_import.py | chunk_builder, corpus_ingestor, incremental_manifest, keyword_index, normalizer, structure_parser, vector_index | legal_ingestion_orchestrator, legal_qualified_import |
| legal_boundary_common.py | legal_extractor, legal_intermediate | legal_content_boundary, legal_s2_boundary, legal_s3_boundary |
| legal_content_boundary.py | corpus_ingestor, legal_boundary_common, legal_extractor, legal_ingestion_models, legal_intermediate | legal_strategy_registry, legal_ingestion_orchestrator |
| legal_extractor.py | legal_ingestion_models | boundary_common, content/s2/s3, intermediate, strategy_registry, word_extractor, quality_gates, orchestrator |
| legal_ingestion_batch.py | legal_quality_gates | legal_ingestion_orchestrator |
| legal_ingestion_inventory.py | legal_ingestion_models | legal_ingestion_orchestrator |
| legal_ingestion_orchestrator.py | chunk_builder, corpus_ingestor, incremental_import, legal_* 全系列, structure_parser | — |
| legal_intermediate.py | legal_extractor, legal_ingestion_models | chunk_builder, structure_parser, boundaries, quality_gates, orchestrator |
| legal_qualified_import.py | incremental_import | legal_ingestion_orchestrator |
| legal_quality_gates.py | legal_extractor, legal_ingestion_models, legal_intermediate, structure_parser | legal_ingestion_batch, legal_ingestion_orchestrator |
| legal_s2_boundary.py | corpus_ingestor, legal_boundary_common, legal_extractor, legal_ingestion_models, legal_intermediate | legal_strategy_registry, legal_ingestion_orchestrator |
| legal_s3_boundary.py | 同 s2 依赖 | legal_strategy_registry, legal_ingestion_orchestrator |
| legal_source_classifier.py | legal_textutil, legal_ingestion_models | legal_ingestion_orchestrator |
| legal_strategy_registry.py | legal_content_boundary, legal_s2_boundary, legal_extractor, legal_ingestion_models | legal_ingestion_orchestrator |
| legal_textutil.py | — | legal_source_classifier, legal_word_extractor |
| legal_word_extractor.py | legal_textutil, legal_extractor, legal_ingestion_models | legal_ingestion_orchestrator |
| normalizer.py | corpus_ingestor | incremental_import |
| retriever.py | embedder, keyword_index, query_normalizer, vector_index, vector_store | （仅被 api 层消费） |
| structure_parser.py | legal_intermediate | chunk_builder, incremental_import, legal_quality_gates |
| vector_index.py | embedder, vector_store | incremental_import, retriever |
