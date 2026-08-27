---
mode: learning
generated_at: 2026-08-27
---

# tests/

## Summary

tests/ 是消防法律 RAG 系统的全量测试层：unit 覆盖 api/core/docs/services 分层的离线摄取管线与在线问答服务，integration 覆盖 FastAPI 端点全链路与 W-S1/S2/S3 真实文件摄取、增量导入及批处理 CLI，fixtures 提供各阶段最小样本数据。

## Task Guide

| 任务 | Domain | Target | Also Check |
|---|---|---|---|
| 理解切块（chunk）构建逻辑如何被测试 | 切块构建 | `tests/unit/services/test_chunk_builder.py` | `tests/integration/pipeline/test_ws1_ingestion_real.py` |
| 理解 S1/S2/S3 内容边界策略的判定差异与送审语义 | 边界策略 | `tests/unit/services/test_legal_content_boundary.py`、`test_legal_s2_boundary.py`、`test_legal_s3_boundary.py` | `test_legal_boundary_common.py` |
| 理解法律质量门（quality gates）的完整判定矩阵 | 质量门 | `tests/unit/services/test_legal_quality_gates.py`（见 `.analysis.md` L497-L1188） | `test_legal_qualified_import.py` |
| 了解增量导入的冲突检测、staging 隔离与失败回滚保护 | 增量导入 | `tests/unit/services/test_incremental_import.py` | `tests/integration/pipeline/test_incremental_import_pipeline.py`、`test_ws2_qualified_incremental_import.py` |
| 理解摄取编排器如何按独立轴解析策略并映射失败 | 摄取编排 | `tests/unit/services/test_legal_ingestion_orchestrator.py` | `test_legal_strategy_registry.py`、`test_legal_ingestion_batch.py` |
| 了解 W-Sx 真实文件的端到端摄取与语料质量验证方式 | 真实链路集成 | `tests/integration/pipeline/test_ws1_ingestion_real.py`、`test_ws1_legal_corpus_quality.py` | `test_todo_ws1_scope.py`、`test_ws3_formal_index_state.py` |
| 了解会话轮次服务的上下文继承、自动标题与流式行为 | 对话管理 | `tests/unit/services/test_conversation_turn_service.py` | `test_context_manager.py`、`test_turn_classifier.py`、`test_conversation_presenter.py` |
| 理解答案生成的证据绑定与多厂商客户端容错测试 | 答案生成 | `tests/unit/services/test_answer_service.py` | `tests/integration/api/test_chat_api.py` |
| 了解 API 层聊天与会话端点的集成契约 | API 集成 | `tests/integration/api/test_chat_api.py`、`test_conversations_api.py` | `tests/unit/api/` |
| 了解离线构建管线一次性产出全部索引工件的验收方式 | 构建管线 | `tests/integration/pipeline/test_build_pipeline.py` | `tests/unit/services/test_vector_index.py` |

## Subdirectories

| Dir | Domain | Depends On | Purpose |
|---|---|---|---|
| `unit/` | 单元测试 | app.api, app.core.settings, app.services, docs/ | 四个分层：api（FastAPI 依赖注入接线）、core（Settings 路径派生）、docs（W-S1 计划文档合规校验）、services（最大主体：法律摄取管线 legal_* 系列、切块/解析、索引检索、对话管理、答案生成共 36 个文件） |
| `integration/` | 集成测试 | app.main, app.services, scripts 入口 CLI | 两个方向：api（TestClient 驱动的聊天/会话/健康端点全链路）、pipeline（W-S1/S2/S3 真实文件摄取、合格增量导入的回滚矩阵、批处理 CLI、todo 基线范围推导、正式索引状态断言） |
| `fixtures/` | 测试数据 | app.services（被样本间接驱动） | 离线管线各阶段最小样本：`raw/`（真实 doc/docx 二进制）、`normalized/` 与 `structured/`（清洗前后文本片段）、`legal_ingestion/todo_baseline.json`（14 文件基线清单）；`chunks/` 目前为空占位 |

### unit/api

| File | Domain | Function |
|---|---|---|
| test_chat_dependencies.py | 依赖注入 | 验证 chat 依赖构建 Retriever 时先预热 embedder 再加载向量存储 |
| test_conversation_dependencies.py | 依赖注入 | 验证会话相关 FastAPI 依赖按 Settings 数据库路径组装 Service/TurnService/C repository 等对象 |

### unit/core

| File | Domain | Function |
|---|---|---|
| test_settings.py | 配置 | 验证 Settings 默认路径构建、空 embedding_max_seq_length 视为 None、会话默认值与增量导入路径从 data_dir 派生 |

### unit/docs

| File | Domain | Function |
|---|---|---|
| test_ws1_plan_docs.py | 文档规范 | 校验 W-S1 计划同步文档行数上限、相对链接有效、索引登记、阅读规则声明与 README 统一 CLI 列举 |

### unit/services

| File | Domain | Function |
|---|---|---|
| test_answer_service.py | 答案生成 | 验证 build_answer 无证据/引用越界即拒答、错误详情透传，及 OpenAI 客户端的 JSON schema、iflow/volcengine 字段归一、markdown 围栏解析与限流重试 |
| test_chat_client.py | 答案生成 | 验证 `_build_response_format` 按 base_url 在 json_schema/json_object 间选择安全格式 |
| test_chunk_builder.py | 切块构建 | 验证 chunk 保留条款路径与元数据、长条款按段落无损切分，及 intermediate chunks 对 source contract、digest 失配、S2/S3 元数据的传播与拒绝 |
| test_context_manager.py | 对话管理 | 验证上下文保留近轮并叠加历史摘要，摘要缺失时降级为仅近轮 |
| test_conversation_presenter.py | 对话管理 | 验证法律依据变化时切换条款文本、不变时复用旧文案，拒答不标记纠正提示 |
| test_conversation_repository.py | 对话管理 | 验证会话仓库 SQLite 往返持久化、软删除后禁止写快照、拒绝跨会话消息引用 |
| test_conversation_service.py | 对话管理 | 验证首条用户消息自动命名、列表按最后消息时间倒序、重命名与软删除 |
| test_conversation_summary.py | 对话管理 | 验证较老轮次压缩生成 history summary |
| test_conversation_turn_service.py | 对话管理 | 验证轮次应用服务：上下文提示触发重检索、范围扩展保留前题、自动标题与轮次元数据落库、流式事件序列、模型失败抛 ChatCompletionError |
| test_turn_classifier.py | 对话管理 | 验证代词追问继承标题、范围扩展追问不强制沿用上一条文 |
| test_corpus_ingestor.py | 语料发现 | 验证 discover_documents 生成稳定排序 manifest、忽略不支持文件、ASCII slug 与非 ASCII 名哈希回退 |
| test_incremental_import.py | 增量导入 | 验证 preflight 对正式产物/manifest/关键词库/向量图四类冲突的失败检测、run 级隐藏 staging 目录隔离写入、提交各步失败的回滚与部分发布防护 |
| test_incremental_manifest.py | 增量导入 | 验证 manifest 追加对同一文档只记录一次 |
| test_knowledge_version.py | 增量导入 | 验证知识版本随工件内容稳定派生且内容变更即改变 |
| test_keyword_index.py | 检索索引 | 验证 SQLite 关键词检索命中条文、地区过滤，及 append 无需重建既有行 |
| test_vector_index.py | 检索索引 | 验证向量索引构建/追加的映射持久化与重复文档拒绝、编码先于加载、SentenceTransformerEmbedder 双编码器选择、FAISS 缺依赖报错清晰、build_indexes 同时产出关键词+向量工件 |
| test_retriever.py | 检索服务 | 验证 fuse_results 按 chunk_id 去重、元数据提示过滤与单权威标题定界，并用真实 WS1 已入库条文做端到端命中 |
| test_query_normalizer.py | 检索服务 | 验证消防法规别名扩展、地区/条号/施行日期抽取、基于上下文提示的追问改写 |
| test_legal_boundary_common.py | 法律文本基础 | 验证标题归一、中文数字转整数、条号提取、章节/页面尾注/页脚模式识别与 FindTailBoundary |
| test_legal_content_boundary.py | 边界策略 | 验证 S1 边界：唯一标题+连续条文确认、正文中印刷字样保留、复制分发页脚与公文发布模板排除、歧义证据送审 |
| test_legal_s2_boundary.py | 边界策略 | 验证 S2（修订汇编类）边界：前置出版材料排除、修订决定条文不计正文、第二标题选择、双候选送审、证据 span 指向抽取块 |
| test_legal_s3_boundary.py | 边界策略 | 验证 S3（表单类）边界：尾部材料吸收、正文中提及附件不得误截断、表单系列识别、模糊标题匹配与多重送审条件 |
| test_legal_extractor.py | 抽取契约 | 验证 ExtractionRequest/Result 的证据携带与 run_id、px 禁止与 digest 失配拒绝、页/块序稳定校验、失败必须结构化 |
| test_legal_word_extractor.py | 抽取契约 | 验证 Word 抽取保持行/空行/块序且只读、非 W 请求拒绝、源文件变更返回结构化失败 |
| test_legal_textutil.py | 抽取契约 | 验证 textutil 子进程使用固定安全命令、非零退出码与 stderr 被保留 |
| test_legal_ingestion_models.py | 数据模型 | 验证分类/摄取枚举稳定值、SourceRef 不可变且拒绝不安全相对路径、IngestionInput 单一输入模式约束 |
| test_legal_intermediate.py | 中间产物 | 验证仅 confirmed 中间产物可写盘、核心不变量违规拒绝、源 digest 变更即失效、metadata_evidence 字段与 span 约束 |
| test_legal_ingestion_inventory.py | 批次清单 | 验证 freeze_batch_input 递归排序、绝对路径+大小+sha256 记录、缺失/空输入/符号链接/哈希期间源变更的拒绝 |
| test_legal_ingestion_batch.py | 批次清单 | 验证批次状态机全部合法迁移与非法迁移/digest 失配拒绝、质检报告一次性写入防覆盖禁键、批次报告读写与汇总计数 |
| test_legal_strategy_registry.py | 摄取编排 | 验证默认注册表暴露全部稳定键及显式状态、独立轴策略注册组合、kind 不匹配/重复/组合键/px 键拒绝 |
| test_legal_ingestion_orchestrator.py | 摄取编排 | 验证编排器按轴独立解析策略组合、异常与 digest 失配映射 failed、unsupported/组合缺失短路、dry-run 对 S2/S3 送审跳过下游且不产生正式写入 |
| test_structure_parser.py | 结构解析 | 验证条文/章节抽取、实际法名优先于前言、括号内带间隔日期、行内超链接清理，及 parse_legal_intermediate 绑定 confirmed 元数据/span 与 S2/S3 目标元数据偏好 |
| test_legal_qualified_import.py | 合格导入 | 验证 commit 前拒绝 processing/review_required/failed 状态及 source/staged/质检报告三方 digest 失配，合格时才委托底层提交并保留源文件类型 |
| test_legal_quality_gates.py | 质量门 | S1/S2/S3 质量门完整判定矩阵：digest/ID 一致性、条文完整性与重复、证据 span、尾部排除区顺序/覆盖、输出纯度与送审语义 → see test_legal_quality_gates.py.analysis.md |

### integration/api

| File | Domain | Function |
|---|---|---|
| test_chat_api.py | API 集成 | 验证首页/会话页渲染同一 shell、新建会话按钮不建空会话，及 /chat 端点的结构化答案、无证据拒答、索引未就绪 503 |
| test_conversations_api.py | API 集成 | 验证创建会话→发消息返回 assistant payload、会话管理端点往返、模型调用失败返回 502 |
| test_health_api.py | API 集成 | 验证健康检查端点返回 OK |

### integration/pipeline

| File | Domain | Function |
|---|---|---|
| test_build_pipeline.py | 构建管线 | 以假 embedder 端到端跑 build，验证 normalized/structured/chunks/关键词库/向量库工件在 tmp 目录齐全 |
| test_incremental_import_cli.py | 增量导入 CLI | 验证 import-new-corpus CLI 要求显式单一来源、拒绝位置与选项混用、裁剪空白并正确接线 settings/embedder |
| test_incremental_import_pipeline.py | 增量导入 | 验证新法规追加不破坏既有索引、重复文档失败零新增行、WS1 合格追加保序 |
| test_incremental_import_real_smoke.py | 增量导入 | 真实 docx 增量导入冒烟：跑通后以关键词+向量检索验证可用 |
| test_legal_extractors_real.py | 真实基线验证 | 验证真实基线文件的抽取请求均解析到彼此独立的 unsupported 策略键 |
| test_legal_source_classifier_real.py | 真实基线验证 | 验证真实 Word 源文件的分类轴（签名/content signals）符合保守预期 |
| test_todo_ws1_scope.py | W-Sx 范围推导 | 验证 todo 基线冻结出同样的 14 文件清单、与真实源一致并唯一派生 WS1 范围 |
| test_todo_ws2_scope.py | W-Sx 范围推导 | 验证 WS2 范围由唯一基线派生且不存在第二个候选基线或辅助函数 |
| test_todo_ws3_scope.py | W-Sx 范围推导 | 验证基线恰含一个 WS3 条目、其源文件只读且被判为 W-S3 |
| test_ws1_batch.py | 批处理 CLI | 验证 WS1 批处理 verify 仅计八文件、dry-run 不发布正式工件但写质检报告、manifest 与单源互斥、拒绝路径穿越 |
| test_ws1_batch_report_real.py | 批次报告 | 验证 WS1 基线恰好选中八个文件且源文件存在并匹配基线记录 |
| test_ws1_ingestion_real.py | 真实摄取链路 | 验证真实 WS1 文件经 Word 抽取（不持久化候选文本）→S1 边界→解析→chunk 全链路输出干净且风险不隐藏 |
| test_ws1_legal_corpus_quality.py | 语料质量门 | 参数化验证 WS1 全部八个用例通过 evaluate_legal_quality 评估 |
| test_ws1_qualified_incremental_import.py | 合格增量导入 | 验证 WS1 八文件合格导入全部提交、重复导入拒绝、批内单文件失败被隔离 |
| test_ws2_batch.py | 批处理 CLI | 验证 WS2 两文件 dry-run auto-pass、pt+s2 类别过滤被拒且无写入、显式参数与默认等价性、无效类别与空选择报告 |
| test_ws2_batch_report_real.py | 批次报告 | 验证真实 WS2 dry-run 报告符合预期且无正式写入 |
| test_ws2_formal_index_state.py | 正式索引状态 | 验证正式索引状态反映已导入的 WS1/WS2 文档 |
| test_ws2_ingestion_real.py | 真实摄取链路 | 验证真实 WS2：河北文件排除 attachment2 与修订材料、社消文件选第二标题并携带机关日期证据、structured/chunks 干净 |
| test_ws2_legal_corpus_quality.py | 语料质量门 | 参数化验证 WS2 两个 Word 用例通过质量门 |
| test_ws2_qualified_incremental_import.py | 合格增量导入 | 验证 WS2 两文件提交、staged digest 失败被隔离、索引发布失败触发回滚 |
| test_ws3_batch.py | 批处理 CLI | 验证 WS3 单文件 verify/dry-run auto-pass、无类别过滤默认仍选 WS1、ps+s3 dry-run 送审不写入、空选择零报告 |
| test_ws3_batch_report_real.py | 批次报告 | 验证 WS3 v3 dry-run 报告 pass 且无正式写入、临时目录真实导入冻结干净的 chunk 数 |
| test_ws3_formal_index_state.py | 正式索引状态 | 验证 WS3 正式工件存在、计数按预期增量、structured/chunks 干净、关键词检索命中目标条文而不命中尾部材料、WS1/WS2 文档仍可检索 |
| test_ws3_ingestion_real.py | 真实摄取链路 | 验证真实 WS3 文件边界确认 excluded_ranges 且 structured/chunks 干净 |
| test_ws3_legal_corpus_quality.py | 语料质量门 | 参数化验证 WS3 单用例通过质量门 |
| test_ws3_qualified_incremental_import.py | 合格增量导入 | 验证 WS3 单文件提交及 source digest/staged digest/索引发布/manifest 发布四级失败的逐一回滚，及 force-batch 报告 |

## File Dependencies

| File 组 | 被测目标（app/scripts 模块） |
|---|---|
| unit/api + integration/api | `app.api.chat`、`app.api.conversations`、`app.main.create_app` |
| unit/services 对话组（conversation_*、context_manager、turn_classifier、presenter） | `app.services.conversation_*`、`context_manager`、`turn_classifier`、`chat_client` |
| unit/services 摄取组（legal_*、structure_parser、chunk_builder、corpus_ingestor、normalizer、legal_textutil） | `app.services.legal_extractor/boundary/s2/s3/ingestion_orchestrator/batch/inventory/qualified_import/quality_gates/strategy_registry`、`structure_parser`、`chunk_builder` |
| unit/services 索引检索组（keyword_index、vector_index、retriever、query_normalizer、incremental_import/manifest、knowledge_version） | `app.services.keyword_index`、`vector_index`/`vector_store`/`embedder`、`retriever`、`query_normalizer`、`incremental_import`、`incremental_manifest`、`knowledge_version` |
| integration/pipeline | 上述离线模块的端到端组合 + 统一 CLI（import-new-corpus、build、batch 命令）|
| unit/docs | docs/ 下 W-S1 计划同步文档、阅读规则文档与 README |
