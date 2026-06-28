# 消防问答 NDJSON 状态流设计

**最后更新：** 2026-04-24

**文档状态：** 已实现并验证到当前范围。

**适用范围：** 消防问答系统 2.0 的会话消息发送链路、前端等待态、最终回答呈现和相关测试验收。

## 目标

本设计把当前一次性消息发送体验升级为：**后端 NDJSON 状态流，最终可信结果由前端逐字呈现**。

目标包括：

- 用户发送问题后，前端能持续感知后端已接收、正在检索、正在生成、正在整理证据和已完成。
- 后端只在完成模型完整 JSON 获取、schema 校验、引文校验、presenter 证据筛选和持久化后，才发送最终可信结果。
- 前端不展示任何未校验草稿，只基于 `completed.assistant` 的可信 payload 做客户端逐字呈现。
- 保留一次性消息接口，避免破坏现有调用方和回归测试。

## 非目标

本期明确不做以下能力：

- 不做模型 token 原生流。
- 不展示未校验草稿。
- 不做 `SSE` 或 `WebSocket`。
- 不做未校验 `delta`。
- 不持久化 `partial message` 或 `delta`。
- 不新增 `delta` 表。
- 第一版不做幂等重试。

这意味着“逐字呈现”只发生在前端拿到最终可信 payload 之后，不代表模型输出曾以 token 形式暴露给用户。

## 现有链路约束

当前主链已经存在：

- 会话创建、列表、详情、重命名和软删除。
- 一次性消息发送：`POST /api/conversations/{conversation_id}/messages`。
- 状态流消息发送：`POST /api/conversations/{conversation_id}/messages/stream`。
- `UserMessageInput` 请求体，字段为 `message`。
- `SendConversationMessageResponse.assistant` 展示结构。
- 会话服务层完成追问判定、上下文裁剪、查询改写、检索、回答生成、presenter 整理和快照落库。
- 前端首页首问链路已按“先创建会话，再发送消息”工作。

当前状态流实现不得绕过这些链路。它应复用同一套服务层编排与最终展示 schema，而不是复制一条新的回答生成逻辑。

## API 与事件协议

### 请求

状态流接口：

```http
POST /api/conversations/{conversation_id}/messages/stream
Content-Type: application/json
```

请求体复用 `UserMessageInput`：

```json
{"message":"消防法关于消防安全责任制怎么规定？"}
```

首页首问仍按现有流程先调用：

```http
POST /api/conversations
```

创建会话后，再调用：

```http
POST /api/conversations/{conversation_id}/messages/stream
```

一次性兼容接口继续保留：

```http
POST /api/conversations/{conversation_id}/messages
```

### 响应

流式状态接口响应头必须为：

```http
Content-Type: application/x-ndjson; charset=utf-8
```

响应体规则：

- 每行一个完整 JSON 事件。
- 每个事件以换行符分隔。
- JSON 字符串内的正文换行必须由 JSON 编码转义。
- 前端解析必须使用 buffer 累积字节或文本片段，不能假设一次 `read()` 就等于一行。

### 事件类型

对外序列化事件主契约固定为：

- `type`
- `message`
- `persisted`
- `retryable`
- `assistant`
- `code`

其中 `type` 为必填，其他字段按事件类型按需出现。`ConversationStreamEvent` 内部仍可保留 `event/data` 作为旧单测和服务层读取的最小兼容层，但它们不属于对外协议，也不应继续写入文档或验收口径。

事件类型固定为：

- `received`
- `retrieving`
- `generating`
- `organizing_evidence`
- `completed`
- `error`

`received` 只表示后端已接受请求，并且已经成功持久化用户消息。它必须携带 `persisted: true`，并可附带用户可读的 `message`：

```json
{"type":"received","message":"已收到问题。","persisted":true}
```

`retrieving` 表示正在检索法规证据：

```json
{"type":"retrieving","message":"正在检索最新法规证据。"}
```

`generating` 表示正在调用模型并等待完整结构化回答：

```json
{"type":"generating","message":"正在生成结构化回答。"}
```

`organizing_evidence` 表示正在进行 schema 校验、引文校验、证据筛选和展示结构整理：

```json
{"type":"organizing_evidence","message":"正在整理法律依据和条文原文。"}
```

`completed.assistant` 等价于现有 `SendConversationMessageResponse.assistant`。字段固定为：

- `message_id`
- `answer`
- `legal_basis`
- `clause_texts`
- `correction_notice`
- `created_at`

示例：

```json
{"type":"completed","assistant":{"message_id":"msg-2","answer":"单位的主要负责人是本单位的消防安全责任人。","legal_basis":["《中华人民共和国消防法》第十六条"],"clause_texts":[{"path":"中华人民共和国消防法 > 第二章 火灾预防 > 第十六条","text":"机关、团体、企业、事业等单位应当履行下列消防安全职责..."}],"correction_notice":"","created_at":"2026-04-23T10:00:00Z"}}
```

`error` 用于流已经开始后的错误。`code` 至少包括：

- `conversation_not_found`
- `index_not_ready`
- `model_error`
- `validation_error`
- `persistence_error`
- `internal_error`

示例：

```json
{"type":"error","code":"model_error","message":"模型调用失败，请稍后重试。","retryable":true}
```

## 服务层编排

后端必须保证事件含义与真实链路一致：

1. 接收 `UserMessageInput`。
2. 校验会话存在和请求体合法性；若流尚未开始，可直接返回 `404` 或 `422`。
3. 检查索引与检索依赖可用性；若流尚未开始，可直接返回 `503`。`get_retriever()` 必须把 `MissingEmbeddingDependencyError` / `MissingVectorStoreDependencyError` 以及普通初始化异常统一映射为 `503`，不得泄漏裸 `500`。当初始化异常来自检索器构建过程时，错误详情应收敛为 `检索器初始化失败：<原始错误>`。
4. 持久化用户消息。
5. 发送 `received`，且 `persisted` 必须为 `true`。
6. 发送 `retrieving`，执行追问判定、上下文裁剪、查询改写和检索。
7. 发送 `generating`，调用模型并等待完整 JSON。
8. 发送 `organizing_evidence`，完成模型完整 JSON 解析、schema 校验、引文校验、presenter 证据筛选。
9. 在发送 `completed` 前，完成 assistant message、turn、answer snapshot 和 history summary 落库。
10. 发送 `completed`。

后端不得在 `completed` 前发送任何回答正文片段。若第 5 步之后失败，使用 `error` 事件收束；若失败发生在流开始前，允许返回 HTTP 错误。

一次性接口 `/api/conversations/{conversation_id}/messages` 继续走同一套最终回答链路。它不需要暴露中间状态，但最终 `assistant` payload 必须与 `completed.assistant` 保持同构。

## 前端状态机

前端状态事件只更新提示文字，不生成正文。

推荐状态顺序：

1. `submitting`
2. `received`
3. `retrieving`
4. `generating`
5. `organizing_evidence`
6. `typewriting`
7. `complete`
8. `error`

前端收到 `completed` 后，按以下顺序做客户端逐字呈现：

1. `answer`
2. `legal_basis`
3. `clause_texts.path`
4. `clause_texts.text`

逐字呈现期间，不得立即调用 `loadConversationDetail` 覆盖本地状态。逐字呈现完成后，可以刷新会话列表；若必须刷新详情，应延后到本地呈现完成之后，并避免闪烁或重复消息。

重复提交必须被抑制。若流式请求失败，输入框应保留原始输入内容，并提示用户重试可能产生新的用户消息。

## 错误与恢复

流开始前允许直接返回：

- `404`：会话不存在。
- `422`：请求体不合法。
- `503`：索引未就绪、检索依赖缺失，或普通检索器初始化异常。当前除 `MissingEmbeddingDependencyError` 与 `MissingVectorStoreDependencyError` 外，也覆盖 `OSError('hf download failed')` 这类初始化异常；它们都必须在 pre-stream 阶段被统一映射为 `503`，并返回 `检索器初始化失败：<原始错误>` 这一类明确详情。

流开始后必须用 `error` 事件表达失败。错误事件至少携带：

- `type`
- `code`
- `message`
- `retryable`

失败后可能已经落库用户消息。第一版不做幂等重试，因此错误提示必须说清楚：再次发送可能产生新的用户消息。前端不得自动重发。

## 测试与验收

服务层测试：

- 覆盖事件顺序：`received -> retrieving -> generating -> organizing_evidence -> completed`。
- 覆盖流式接口和一次性接口共享同一条最终回答链路。
- 覆盖 `completed.assistant` 与现有一次性响应 assistant 结构一致。
- 覆盖模型失败、schema 校验失败、持久化失败时的 `error` 事件。

API 测试：

- 使用 `TestClient.stream` 验证 `Content-Type` 为 `application/x-ndjson; charset=utf-8`。
- 验证每行都是完整 JSON。
- 验证 `received.persisted` 为 `true`。
- 验证流开始前的 `404 / 422 / 503`；当前已补 `422` 集成测试。`503` 既覆盖索引未就绪，也覆盖 `MissingEmbeddingDependencyError` / `MissingVectorStoreDependencyError` 这类检索依赖缺失路径，以及普通初始化异常路径。
- 验证流开始后的 `error.code` 至少覆盖 `conversation_not_found`、`index_not_ready`、`model_error`、`validation_error`、`persistence_error`、`internal_error` 中的关键路径。

前端测试：

- 覆盖 buffer 解析，不能把一次 `read()` 当作一行。
- 覆盖正文换行由 JSON 转义后仍能正确呈现。
- 覆盖状态事件只更新提示文字。
- 覆盖 `completed` 后按 `answer -> legal_basis -> clause_texts.path/text` 的顺序逐字呈现。
- 覆盖 typewriter 期间不立即 `loadConversationDetail` 覆盖本地状态。
- 覆盖错误态、保留输入、重复提交抑制。

真实验证：

- 使用真实 `data/index/`。
- 使用 fake chat client，避免真实模型波动导致验收不稳定。
- 覆盖至少一轮首问和一轮追问。
- 当前已验证到“真实 `data/index/retrieval.db` + fake chat client”范围：流式返回 `received/retrieving/generating/organizing_evidence/completed`，最终回答与历史写回正常。
- 当前未纳入本轮通过口径的是“真实向量检索 + 真实 embedder warmup” smoke；它在当前环境会受 Hugging Face 网络可用性影响，可能报 SSL / closed client 相关异常，属于外部依赖风险。

浏览器 E2E：

- 无需新增依赖；先在 `fire` 环境确认 Playwright 可用。
- 若 Playwright 在 `fire` 环境可用，使用 Chromium 跑关键路径 E2E。
- E2E 通过 `page.route` mock `/api/conversations*` 的可控 NDJSON，避免真实模型或真实索引导致 flaky。
- 为关键 DOM 补 `data-testid`，让测试依赖稳定语义而不是视觉样式。
- `trace` 和 `screenshot` 只在失败时保留。
- 不得依赖 `waitForTimeout`，应等待明确的 DOM 状态、响应或事件。
- 若 Playwright 在 `fire` 环境不可用，记录阻塞，不私自安装。当前 `e2e-runner` 未完成浏览器验收的直接原因不是应用后端没启动，而是 Codex 内置浏览器 `iab` backend 不可发现；本地后端实际已启动，`curl http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`。

## 实现与验证依赖

本设计无需新增依赖，沿用现有 `fire` 环境。

当前实现与继续验证时需要确认：

- `fire` 环境可运行现有 Python、FastAPI、pytest 依赖。
- `data/index/` 已存在真实索引产物，供真实验证使用。
- 如需浏览器 E2E，先在 `fire` 环境确认 Playwright 可用；不可用则记录阻塞，不安装。

## 风险与规避

- 风险：前端把状态流误做成模型 token 流。规避：文档、schema 和测试都固定为状态事件 + 最终可信 payload。
- 风险：流式接口复制一次性接口逻辑，导致两条链路行为分叉。规避：服务层应共享最终回答链路，API 只负责事件包装。
- 风险：前端按 read chunk 直接解析 JSON，遇到半行或多行合并时失败。规避：测试覆盖 buffer 解析。
- 风险：`completed` 先发送、落库后执行，导致刷新历史看不到最终回答。规避：后端必须在发送 `completed` 前完成全部落库。
- 风险：错误后自动重试产生重复用户消息。规避：第一版不做幂等重试，前端只提示人工重试风险。
- 风险：E2E 依赖真实模型和真实索引导致 flaky。规避：Playwright 使用 `page.route` mock 可控 NDJSON。
