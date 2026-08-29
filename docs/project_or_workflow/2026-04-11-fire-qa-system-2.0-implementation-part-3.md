# 消防问答系统 2.0 实施计划（分卷三）

> 状态：历史实施记录。本文中的 `error.code` 验收清单为历史口径，不作为后续 feature 的执行参考；现行契约以 [消防问答系统PRD](../architecture_or_strategy/消防问答系统PRD.md) 与 [NDJSON 状态流设计](../architecture_or_strategy/2026-04-23-fire-qa-ndjson-status-stream-design.md) 为准。

> 本文为实施计划分卷三；分卷导航见[实施计划总览](./2026-04-11-fire-qa-system-2.0-implementation.md)。

## 流式状态专项阶段（尚未实现）

本阶段只处理“后端 NDJSON 状态流，最终可信结果由前端逐字呈现”。不得把本阶段实现成模型 token 原生流、未校验草稿流、`SSE`、`WebSocket` 或未校验 `delta`。

依赖情况：**无需新增依赖，沿用当前 `fire` 环境。** Playwright 当前按用户补充可尝试使用；实施前必须先在 `fire` 环境确认 Playwright 可用。若 Playwright 在 `fire` 环境不可用，记录阻塞，不私自安装。

### 专项任务 1：固定 NDJSON 事件协议与共享服务链路

**涉及文件：**

- 修改：`app/schemas/conversation.py`
- 修改：`app/services/conversation_turn_service.py`
- 新增或修改：`tests/unit/services/test_conversation_turn_service.py`

**测试先行：**

- 先写服务层事件序列测试，期望顺序为 `received -> retrieving -> generating -> organizing_evidence -> completed`。
- 验证 `received` 只在用户消息成功持久化后出现，并且携带 `persisted: true`。
- 验证 `completed.assistant` 与现有 `SendConversationMessageResponse.assistant` 同构，字段固定为 `message_id`、`answer`、`legal_basis`、`clause_texts`、`correction_notice`、`created_at`。
- 验证一次性接口和流式接口复用同一条最终回答链路，不复制回答生成逻辑。

**实现要求：**

- 服务层可以暴露事件生成器或等价抽象，但最终回答必须继续经过模型完整 JSON、schema 校验、引文校验、presenter 证据筛选。
- 后端必须在发送 `completed` 前完成 assistant message、turn、answer snapshot 和 history summary 落库。
- repository 不保存 `partial message` 或 `delta`，不新增 `delta` 表。
- 状态事件不携带回答正文片段。

**验证命令：**

```bash
conda run -n fire python -m pytest tests/unit/services/test_conversation_turn_service.py -q
```

### 专项任务 2：新增流式消息 API

**涉及文件：**

- 修改：`app/api/conversations.py`
- 修改：`tests/integration/api/test_conversations_api.py`

**测试先行：**

- 使用 `TestClient.stream` 调用 `POST /api/conversations/{conversation_id}/messages/stream`。
- 验证响应头为 `Content-Type: application/x-ndjson; charset=utf-8`。
- 验证每行都是完整 JSON 事件，且事件类型只允许 `received`、`retrieving`、`generating`、`organizing_evidence`、`completed`、`error`。
- 验证请求体复用 `UserMessageInput`，字段为 `message`。
- 验证流开始前可返回 HTTP `404 / 503 / 422`。
- 验证流开始后错误通过 `error` 事件表达，`code` 至少覆盖 `conversation_not_found`、`index_not_ready`、`model_error`、`validation_error`、`persistence_error`、`internal_error` 中的关键路径。

**实现要求：**

- 新增 `POST /api/conversations/{conversation_id}/messages/stream`。
- 响应使用 `application/x-ndjson; charset=utf-8`。
- 每行写出一个完整 JSON 事件；正文换行必须由 JSON 编码转义。
- 一次性 `POST /api/conversations/{conversation_id}/messages` 保留兼容。
- 首页首问仍先 `POST /api/conversations` 创建会话，再调用 `/messages/stream`。

**验证命令：**

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -q
```

### 专项任务 3：前端接入状态流与客户端逐字呈现

**涉及文件：**

- 修改：`app/static/app.js`
- 修改：`app/static/app.css`
- 修改：`app/templates/index.html`
- 修改：`tests/integration/api/test_chat_api.py`

**测试先行：**

- 覆盖前端 NDJSON buffer 解析，不能假设一次 `read()` 就是一行。
- 覆盖正文换行由 JSON 转义后仍能正确呈现。
- 覆盖状态事件只更新提示文字，不生成正文。
- 覆盖 `completed` 后按 `answer -> legal_basis -> clause_texts.path/text` 的顺序做客户端逐字呈现。
- 覆盖 typewriter 期间不立即 `loadConversationDetail` 覆盖本地状态；完成后可刷新会话列表，必要时延后刷新详情。
- 覆盖错误态、保留输入内容、重复提交抑制。

**实现要求：**

- 前端发送消息时优先调用 `/messages/stream`。
- 状态事件只更新状态文案。
- `completed.assistant` 到达后，前端基于可信 payload 做逐字呈现。
- 流式失败后提示用户：可能已经落库用户消息，第一版不做幂等重试，重试可能产生新的用户消息。
- 为关键 DOM 补 `data-testid`，服务后续 E2E。

**验证命令：**

```bash
conda run -n fire python -m pytest tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q
```

### 专项任务 4：真实验证与可选 Playwright E2E

**涉及文件：**

- 新增或修改：`tests/e2e/*`（仅在仓库已有 E2E 组织方式或 Playwright 可用时）

**验证要求：**

- 真实验证使用真实 `data/index/` 加 fake chat client，避免真实模型波动导致 flaky。
- 至少覆盖首问和追问各一轮。
- 先在 `fire` 环境确认 Playwright 可用。
- 若可用，使用 Chromium 关键路径 E2E，并通过 `page.route` mock `/api/conversations*` 的可控 NDJSON。
- `trace` 和 `screenshot` 只在失败时保留。
- 不依赖 `waitForTimeout`，只等待明确 DOM 状态、响应或事件。
- 若 Playwright 不可用，记录阻塞，不私自安装。

**验证命令示例：**

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/integration/api/test_chat_api.py -q
```

若项目中已有可运行的 Playwright 测试入口，再补充对应命令；如果没有或 `fire` 环境不可用，不新增依赖，并向用户说明阻塞。

## 最终验证清单

全部任务完成后，最低验收门槛为：

```bash
conda run -n fire python -m pytest -q
conda run -n fire python scripts/build_corpus.py
conda run -n fire python scripts/build_index.py
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

最终预期：

- 会话数据库文件成功落到本机 `var/` 目录
- `/` 渲染双栏会话界面
- `/api/conversations` 可以创建、列出、重命名、删除会话
- `/api/conversations/{id}/messages` 可以处理新问题和追问
- `/api/conversations/{id}/messages/stream` 可以输出 NDJSON 状态事件，并在 `completed.assistant` 中返回可信最终结果
- 前端状态事件只更新提示文字，最终结果由客户端按 `answer -> legal_basis -> clause_texts.path/text` 逐字呈现
- 助手消息只展示回答和法律依据
- 条款原文展示遵守“追问优先关联上一轮、依据变化则切换到本轮并提示修正”的规则
- 服务重启后历史会话仍能恢复
- 多轮上下文不会绕过本轮重新检索

计划入口已迁移至 `docs/project_or_workflow/2026-04-11-fire-qa-system-2.0-implementation.md`。
