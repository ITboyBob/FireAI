# 消防问答系统 2.0

基于 `法律文本/` 的本机消防法规问答系统。当前实现包含离线语料处理、混合检索、OpenAI 兼容聊天后端、本机 `SQLite` 会话持久化，以及由 FastAPI 直接提供的双栏网页会话界面。

详细执行状态只在 [docs/status.md](docs/status.md) 维护。

## 文档权威关系

- [2.0 PRD](docs/plans/2026-04-11-fire-qa-system-2.0-prd.md) 是当前唯一产品标准，负责产品目标、用户范围、功能边界和产品验收口径。
- 本 README 是当前技术标准入口，负责技术架构、目录边界、运行命令、测试规则和工程约束。
- [NDJSON 状态流设计](docs/plans/2026-04-23-fire-qa-ndjson-status-stream-design.md) 是会话消息状态流、最终可信结果逐字呈现、错误恢复和验收口径的专项设计。
- [一期 RAG 设计文档](docs/plans/2026-03-28-fire-law-rag-design.md) 仅作为历史设计资料保留。若旧设计与 2.0 PRD 冲突，产品口径以 PRD 为准；若旧设计与 README 冲突，技术口径以 README 为准。

## 当前能力与已确认基线

- 离线链路：原始 `.doc/.docx` 法规标准化、结构解析、按条优先切块、关键词索引与向量索引构建
- 在线链路：
  - `/api/conversations/*` 提供会话创建、列表、详情、重命名、删除和多轮消息执行
  - 已确认待实现 `POST /api/conversations/{conversation_id}/messages/stream`，使用后端 NDJSON 状态流，最终可信结果由前端逐字呈现
  - 一次性 `POST /api/conversations/{conversation_id}/messages` 保留兼容
  - `/api/chat` 保留为兼容回归入口，模型调用失败时返回明确错误
- 会话能力：本机持久化历史会话、首条消息自动标题、基础追问判定、上下文窗口裁剪、修正提示和回答快照落库
- 网页入口：`/` 提供“会话列表 + 当前线程 + 输入区”的双栏界面，前端主链默认使用 `/api/conversations/*`

## 环境规则

- 所有包安装必须在 conda 环境 `fire` 中执行
- 所有代码执行必须在 conda 环境 `fire` 中执行
- [docs/status.md](docs/status.md) 按需更新：只有重要里程碑、阻塞点变化、用户明确要求、长期任务交接、需要保存验证结果或会影响后续上下文时才写入

## 技术标准

本节承接一期 RAG 设计中仍然有效的技术稳定约束，并作为当前实现和后续改造的技术入口。

### 离线与在线分离

- 离线链路负责语料标准化、结构解析、切块、关键词索引和向量索引构建。
- 在线链路只负责会话、查询规范化、检索、回答生成和结果展示，不得在用户请求过程中临时重建语料、切块或索引。
- 原始语料目录 `法律文本/` 只读；生成物统一落在 `data/` 下，运行时噪声统一落在 `var/` 下。
- 若 `data/index/` 缺失或不可用，在线接口和页面必须返回明确的“尚未完成建库”状态，而不是自动绕过检索或静默改用纯模型回答。

### 建库产物一致性

- `data/normalized/`、`data/structured/`、`data/chunks/` 与 `data/index/` 应来自同一轮离线重建。
- 修改标准化、结构解析、切块、索引构建任一环节后，必须按依赖顺序重建下游产物。
- `scripts/build_corpus.py` 负责重建 `normalized -> structured -> chunks`；`scripts/build_index.py` 负责基于当前 chunks 重建检索索引。
- 每份生成物都应保持可检查、可删除、可重建；不要把人工维护配置混入 `data/` 生成物目录。

### 证据约束

- 回答必须基于当前检索证据生成，不得绕过检索直接让聊天模型自由回答。
- 回答中的法律依据必须能回溯到当前证据集中的 `document_id`、条文路径和条文原文。
- 证据不足、无法绑定引文或模型返回内容无法通过本地结构校验时，必须进入拒答或错误态。
- 多轮追问每轮都应重新检索；当本轮依据相对上一轮发生变化时，展示层必须给出修正提示并切换到最新证据。

### 后端 NDJSON 状态流

- 统一命名为：**后端 NDJSON 状态流，最终可信结果由前端逐字呈现**。
- 状态流接口为 `POST /api/conversations/{conversation_id}/messages/stream`，请求体复用 `UserMessageInput` 的 `message` 字段。
- 响应头必须为 `Content-Type: application/x-ndjson; charset=utf-8`。
- 每行必须是一个完整 JSON 事件；正文换行必须由 JSON 编码转义；前端必须用 buffer 解析，不能假设一次 `read()` 就是一行。
- 事件类型固定为 `received`、`retrieving`、`generating`、`organizing_evidence`、`completed`、`error`。
- `received` 只表示后端已接受请求且已成功持久化用户消息，必须携带 `persisted: true`。
- `completed.assistant` 等价现有 `SendConversationMessageResponse.assistant`，字段固定为 `message_id`、`answer`、`legal_basis`、`clause_texts`、`correction_notice`、`created_at`。
- 后端必须在发送 `completed` 前完成模型完整 JSON、schema 校验、引文校验、presenter 证据筛选、assistant message / turn / snapshot / history summary 落库。
- 本状态流不是模型 token 原生流，不展示未校验草稿，不做 `SSE` 或 `WebSocket`，不做未校验 `delta`，不持久化 `partial message/delta`，不新增 `delta` 表。
- 一次性 `POST /api/conversations/{conversation_id}/messages` 必须保留兼容，并与 `completed.assistant` 保持同构。

### 错误处理

- 建库缺失、检索失败、证据不足、模型调用失败、会话不存在等错误必须拆开表达，不能统一吞成“无法回答”。
- 模型调用失败应暴露为上游服务问题，不能伪造成证据不足。
- 会话历史读取不得触发新的模型调用；只有用户显式发送消息时才进入检索和回答生成链路。
- 删除后的会话不得继续写入消息、轮次或回答快照。
- 状态流开始前可返回 HTTP `404 / 503 / 422`；状态流开始后必须使用 `error` 事件表达失败。
- `error.code` 至少包括 `conversation_not_found`、`index_not_ready`、`model_error`、`validation_error`、`persistence_error`、`internal_error`。
- 失败后可能已经落库用户消息；第一版不做幂等重试，错误后前端应保留输入内容，并提示重试可能产生新的用户消息。

### 测试与真实产物验证

- 新增或修改测试时，必须先运行对应的单元测试或预编写测试，再基于真实上游产物补做验证。
- 涉及离线链路时，真实验证优先使用 `法律文本/`、`data/normalized/`、`data/structured/`、`data/chunks/` 或 `data/index/`。
- 涉及在线链路时，除单元测试外，还应覆盖 `TestClient`、真实索引烟雾验证或真实 HTTP 验证中的至少一种。
- 涉及 NDJSON 状态流时，必须覆盖服务层事件顺序与共享链路、`TestClient.stream` NDJSON、前端 buffer 解析、typewriter、错误态和重复提交。
- 流式状态真实验证使用真实 `data/index/` 加 fake chat client，避免真实模型或真实索引波动导致 flaky。
- 无需新增依赖；先在 `fire` 环境确认 Playwright 可用。若可用，使用 Chromium 关键路径 E2E，并用 `page.route` mock `/api/conversations*` 的可控 NDJSON。`trace` 和 `screenshot` 只在失败时保留，不依赖 `waitForTimeout`。若 Playwright 不可用，记录阻塞，不私自安装。
- 纯文档小改、只读分析或无状态影响的简单任务，不需要自动写入 [docs/status.md](docs/status.md)；若文档变更会改变后续执行规则或交接上下文，则应记录。

### 前端工程组织

- 当前前端由 FastAPI 模板和静态资源直接提供，不默认引入 React、Vue 或其他 SPA 框架。
- 首页态和对话态可以复用同一 HTML 壳，但工程上应保持清晰的页面状态边界，避免把首页组件挂在线程空状态里。
- 输入、跳转、等待态、错误态和历史会话恢复应有稳定的 DOM 标识或可测试契约，方便后续用自动化或手工验收检查。
- 首页首问仍先 `POST /api/conversations` 创建会话，再调用 `/messages/stream`。
- 状态事件只更新提示文字，不生成回答正文。
- 前端收到 `completed` 后，按 `answer -> legal_basis -> clause_texts.path/text` 顺序做客户端逐字呈现。
- typewriter 期间不得立即 `loadConversationDetail` 覆盖本地状态；完成后可刷新会话列表，必要时延后刷新详情。
- 关键交互元素应补稳定 `data-testid`，供 E2E 使用。
- 页面静态资源变更后应继续使用版本戳或等效机制避免浏览器缓存混用旧 CSS/JS。

## 安装

1. 激活或显式使用 `fire` 环境。
2. 在 `fire` 环境安装项目：

```bash
conda run -n fire python -m pip install -e ".[dev]"
```

3. 参考 [.env.example](.env.example) 在本机创建未纳入版本控制的 `.env`，至少补齐：

- `CHAT_API_KEY`
- `CHAT_BASE_URL`
- `CHAT_MODEL`
- `EMBEDDING_MODEL_NAME`

## 建库

先跑离线语料流水线：

```bash
conda run -n fire python scripts/build_corpus.py
```

该步骤会重建：

- `data/normalized/`
- `data/structured/`
- `data/chunks/`

再构建检索索引：

```bash
conda run -n fire python scripts/build_index.py
```

该步骤会重建：

- `data/index/retrieval.db`
- `data/index/faiss.index`
- `data/index/vector_map.json`

## 运行

后端启动命令：

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

若需要显式指定端口，可使用：

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload --port 8000
```

启动后可访问：

- 网站首页：<http://127.0.0.1:8000/>
- 网站首页（等价地址）：<http://localhost:8000/>
- `/`：双栏网页会话界面
- `/health`：健康检查
- `/docs`：FastAPI 文档页

## 测试

任务 11 相关回归：

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q
```

完整回归：

```bash
conda run -n fire python -m pytest -q
```

流式状态专项实现后，至少补充执行：

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/integration/api/test_chat_api.py -q
```

若 `fire` 环境中的 Playwright 可用，再执行项目内约定的 Chromium 关键路径 E2E；E2E 应通过 `page.route` mock `/api/conversations*` 的可控 NDJSON。

## 已知限制

- 当前系统定位仍是“本机单用户会话问答系统”，不包含多用户、权限、会话搜索或跨设备同步。
- 若未先完成建库，网页会直接收到建库未完成提示，而不是自动帮你补建索引。
- 回答层仍依赖外部 OpenAI 兼容聊天服务；若未配置真实 `CHAT_*` 或提供商凭证已失效，只能完成结构、检索、持久化和前端壳验证，无法完成真实多轮回答验收。
- 后端 NDJSON 状态流只表达处理状态和最终可信结果，不提供模型 token 原生流、`SSE`、`WebSocket`、未校验草稿、未校验 `delta` 或 `partial message/delta` 持久化。
- 第一版不做幂等重试；流式失败后重试可能产生新的用户消息。
- 现有切块体系仍保留一条已登记的历史技术债：枚举条文在未超长时不会进一步细拆，引用粒度可能偏粗。

## 仓库结构

- `法律文本/`：原始法规输入
- `app/`：FastAPI 应用、模板和静态资源
- `scripts/`：离线流水线脚本入口
- `data/`：可重建生成物
- `tests/`：单元测试与集成测试
- `docs/plans/`：设计文档与实施计划

## 相关文档

- [文档索引](docs/文档索引.md)
- [项目状态](docs/status.md)
- [产品需求文档（消防问答系统 2.0）](docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)
- [实施计划（消防问答系统 2.0）](docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)
- [NDJSON 状态流设计](docs/plans/2026-04-23-fire-qa-ndjson-status-stream-design.md)
- [一期 RAG 历史设计资料](docs/plans/2026-03-28-fire-law-rag-design.md)
- [一期 RAG 历史实施计划](docs/plans/2026-03-28-fire-law-rag-implementation.md)
