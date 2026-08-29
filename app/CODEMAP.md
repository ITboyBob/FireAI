---
mode: learning
generated_at: 2026-08-27
---

# app/CODEMAP

## Summary

FastAPI 后端「消防问答系统 2.0」：会话管理、证据检索（SQLite 关键词 + FAISS 向量）、法条绑定的答案生成，以及法规摄取/增量导入的质量门禁管线，配套 Jinja2 + 原生 JS Web 界面。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解一次问答请求从 API 到证据检索与答案生成的完整链路 | 问答链路 | api/chat.py → services/retriever.py → services/answer_service.py | schemas/chat.py |
| 理解多轮会话管理与流式事件输出机制 | 会话管理 | api/conversations.py → services/conversation_turn_service.py | services/context_manager.py、services/knowledge_version.py |
| 理解会话的 SQLite 持久化模型与软删除 | 会话存储 | services/conversation_repository.py | services/conversation_service.py |
| 理解向量/关键词双路检索与融合排序 | 检索融合 | services/retriever.py | services/vector_index.py、services/keyword_index.py、services/embedder.py、services/vector_store.py |
| 理解 LLM 客户端封装与引文校验拒答策略 | 答案生成 | services/chat_client.py + services/answer_service.py | schemas/chat.py |
| 理解离线语料构建在服务侧的基础件（发现→清洗→结构→分块） | 语料构建 | services/corpus_ingestor.py、services/normalizer.py、services/structure_parser.py、services/chunk_builder.py | scripts/build_corpus.py |
| 理解增量导入的 staging 校验与提交/回滚机制 | 增量导入 | services/incremental_import.py | services/incremental_manifest.py |
| 理解 W/S1/S2/S3 内容分类边界判定与提取策略 | 摄取边界判定 | services/legal_s2_boundary.py、services/legal_s3_boundary.py、services/legal_content_boundary.py | services/legal_boundary_common.py |
| 理解摄取批处理编排、质量门禁与合格提交 | 摄取管线 | services/legal_ingestion_orchestrator.py | legal_quality_gates.py → see legal_quality_gates.py.analysis.md；services/legal_quality_gates.py |
| 理解配置加载与环境变量入口 | 配置中心 | core/settings.py | .env.example |
| 理解应用装配、路由挂载与启动预热 | 应用装配 | main.py | — |
| 理解前端 SPA 与后端 API 的交互方式 | 前端资产 | static/app.js | templates/index.html |

## Subdirectories

| Dir | Domain | Depends On | Purpose |
| --- | --- | --- | --- |
| api/ | HTTP 路由层 | core, schemas, services, （间接 static/templates 由 main 挂载） | 定义 /api/chat、/api/conversations、健康检查三组路由及依赖注入工厂 |
| core/ | 配置中心 | pydantic-settings | 集中定义 Settings（数据目录、索引目录、会话库路径、LLM 与嵌入模型参数）并提供 get_settings 单例 |
| schemas/ | Pydantic 契约 | pydantic | 聊天请求/响应与会话列表/详情/流式事件的 DTO 定义，作为 api↔services 的数据契约 |
| services/ | 领域服务实现 | core（部分）、schemas | 会话存储、检索融合、答案生成、语料构建、增量导入、法规摄取门禁等全部业务逻辑（38 个文件）；conversation_repository 提供 PersistenceError 与 to_persistence_error 分型（仅 locked 类 OperationalError 瞬时，其余 sqlite3.Error 与 RuntimeError 固有），turn_service 仅对 received 后 4 个写调用与快照守卫经 _persist 包装 |
| static/ | 前端静态资产 | api/（经 fetch 调用 REST 接口） | app.js 实现双视图（首页/会话线程）SPA 与流式消息渲染；app.css 全部样式 |
| templates/ | 页面模板 | static/（注入带版本号的资源 URL） | index.html：单一 Jinja2 外壳模板，承载首页与会话两种视图骨架 |

## Key Exports

| Symbol | Source | Line |
| --- | --- | --- |
| app (FastAPI instance) | main.py | L:71 |
| create_app | main.py | L:38 |
| get_settings | core/settings.py | L:44 |
| Settings | core/settings.py | L:8 |
| router (chat) | api/chat.py | L:21 |
| router (conversations) | api/conversations.py | L:33 |
| get_retriever / get_chat_client | api/chat.py | L:35 / L:58 |
| ChatRequest | schemas/chat.py | L:19 |
| ConversationStreamEvent | schemas/conversation.py | L:72 |
| run_incremental_import | services/incremental_import.py | L:122 |
| run_legal_ingestion | services/legal_ingestion_orchestrator.py | L:305 |
| Retriever | services/retriever.py | L:17 |
| SentenceTransformerEmbedder | services/embedder.py | L:46 |
| ConversationRepository | services/conversation_repository.py | L:71 |
| PersistenceError / to_persistence_error | services/conversation_repository.py | L:71 / L:83 |

## Files

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| \_\_init\_\_.py | 包标识 | — | 空包声明 |
| main.py | 应用装配 | ← api/, core/, templates/, static/；← external fastapi, anyio | create_app 组装 FastAPI：挂载 /static、渲染 Jinja2 外壳页（首页与会话页共用 index.html）、注册 health/chat/conversations 三个 router；lifespan 中预预热 retriever（加载嵌入模型）；静态资源 URL 附 sha256 前 12 位版本号防缓存 |

### Files: api/（源文件不足 4 个，折叠于本图）

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| chat.py | 问答路由 | ← core/settings, schemas/chat, services/{answer_service, chat_client, embedder, retriever, vector_index, vector_store}；→ conversations.py 复用其依赖工厂 | POST /api/chat 单轮问答；提供 get_retriever/get_chat_client 依赖工厂（含索引文件就绪检查 KEYWORD_DB_FILENAME="retrieval.db"、嵌入依赖缺失 503）；独立问答与消费本文件依赖工厂的唯一入口 |
| conversations.py | 会话路由 | ← api/chat（get_chat_client/get_retriever）、core/settings、schemas/conversation、services/{context_manager, conversation_presenter, conversation_repository, conversation_service, conversation_summary, conversation_turn_service, knowledge_version, turn_classifier, chat_client} | 会话 CRUD、重命名、软删除；POST …/messages 同步问答；POST …/messages/stream 经 StreamingResponse 输出 NDJSON 状态事件，错误事件四 code（model_error / internal_error / conversation_not_found / persistence_error）按 received 是否已发出分派（conversation_not_found 仅限 received 前；persistence_error 按 transient 分瞬时/固有两档）；knowledge_version 注入回答快照 |
| health.py | 健康检查 | — | GET /api/health 返回 {"status": "ok"} |

### Files: core/

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| settings.py | 配置中心 | ← external pydantic-settings | Settings 字段：data_dir/raw_corpus_dir/index_dir、conversation_db_path=var/conversations.db、上下文窗口与摘要触发阈值、chat_*（base_url/key/model/timeout/temperature）、embedding_*；属性 manifests_dir=data/manifests、incremental_staging_dir=data/.staging；get_settings 为 lru_cache 单例（读取根目录 .env） |

### Files: schemas/

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| \_\_init\_\_.py | 契约出口 | ← chat.py, conversation.py | 汇出全部 DTO，供外部 `from app.schemas import …` 统一引用 |
| chat.py | 问答契约 | — | EvidenceItem（法条证据）、ChatRequest、ModelAnswer、ChatResponse（继承 ModelAnswer，含 evidence 列表） |
| conversation.py | 会话契约 | — | ConversationListItem/Detail/Message、AssistantMessagePayload、UserMessageInput、RenameConversationInput、SendConversationMessageResponse、ConversationStreamEvent（SSE 事件模型） |

### Files-group: static/ 与 templates/（前端资产）

| File | Domain | Function |
| --- | --- | --- |
| static/app.js | 前端逻辑 | 无框架原生 JS SPA：会话列表/创建/重命名/删除、首页与会话线程双视图切换、通过 fetch 调用 /api/conversations 及 /messages/stream（fetch 流式读取渲染阶段事件），从 workspace dataset 读取注入的初始会话 ID 与 endpoint |
| static/app.css | 前端样式 | 全部界面样式（暗色主题布局、视图切换、错误面板等） |
| templates/index.html | 页面外壳 | 唯一 Jinja2 模板：加载注入的 static_css_url/static_js_url、conversation_endpoint、initial_conversation_id，包含 home-view 与 thread-view 两套 DOM 骨架 |

## File Dependencies

| File | Imports (in-dir) | Exposed To (in-dir) |
| --- | --- | --- |
| main.py | api/chat, api/conversations, api/health, core/settings | templates/index.html（运行时渲染）、static/（挂载） |
| api/conversations.py | api/chat | main.py |
| api/chat.py | core/settings | api/conversations.py |
