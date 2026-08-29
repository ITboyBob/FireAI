# 实施计划：会话错误分支三需求（404 读取区分 / 流中会话竞态删除 / persistence_error 两档）

- 文档性质：本 feature 的工程执行计划，步骤粒度为「一次可独立验证的最小变更」。
- 执行约束：所有安装与代码执行使用 `conda run -n fire ...`；不新增依赖；TDD（先写测试再实现）；全量回归会间接 import DeepEval，必须以 `DEEPEVAL_DISABLE_DOTENV=1` 执行（AGENTS.md 强制规则 2；第二批步骤 14 已实证：不设该变量时仓库 `.env` 会污染 `test_settings_build_default_paths`）；前端行为验收使用 Playwright E2E（环境三件套已按《工程技术标准》就绪：playwright、Chromium、pytest-playwright）。

## 一、背景与范围

### 需求（来自《消防问答系统PRD》交互行为契约与系统接口协议）

1. **需求 1（404 读取分支）**：打开历史会话失败时，前端按 HTTP 状态区分——仅 404 显示「会话不存在或已删除」；其他失败（500/断网等）保留「读取会话失败」类文案，不得声称会话已被删除。
2. **需求 2（会话竞态删除）**：后端在流中（`received` 前）捕获 `ConversationNotFoundError` 时发出 `code="conversation_not_found"`、`message="会话不存在或已删除"`、`retryable=false` 的 error 事件（不再落入 `internal_error` 兜底）；前端收到该 code 时：显示该文案、离开失效会话 URL 回 `/`、刷新会话列表、保留输入框草稿。
3. **需求 3（persistence_error 两档）**：仅对 `received` 之后的 4 个写方法（assistant 消息落库、turn 创建、answer snapshot 保存、history summary 保存）做异常封装，归一为 `PersistenceError(transient: bool)`；瞬时判定仅限 locked 类 `sqlite3.OperationalError`（文案「服务内部异常，请稍后重试。」，`retryable=true`）；其余数据库异常与快照守卫 `RuntimeError` 归固有档（文案「回答无法保存，可能需要管理员检查系统存储或服务状态」，`retryable=false`）；固有档时前端状态行显示「重试也无法恢复本轮回答」，不出现「重试将产生新的提问」；`received` 前的失败（含用户消息落库）仍为 `internal_error`。

### 非目标（明确不做）

- `received` 后持久化链路中的会话删除精确归因不做（设计文档「已知限制」：第一版按 `internal_error` 处理）。
- 固有档无管理员入口（文案提示管理员，但不提供任何管理界面/动作）。
- 不做幂等重试（第一版明确不做，错误后仅保留输入并提示重试风险）。

## 二、权威文档与参考边界

### 权威文档（按优先级）

1. `docs/architecture_or_strategy/消防问答系统PRD.md`：产品契约。重点：`系统接口协议`（L149-L151）、`交互行为契约` 新增 3 条（L125-L127）、`测试决策` 新增 3 条验收（L185-L187）。
2. `docs/architecture_or_strategy/工程技术标准.md`：`error.code` 口径（L63-L65）与 `PersistenceError` 实现口径（L66），以及前端工程组织与测试要求。
3. `docs/architecture_or_strategy/2026-04-23-fire-qa-ndjson-status-stream-design.md`：NDJSON 契约、四 code 清单（L159-L166）与「已知限制」（L168）。
4. 仓库根 `CODEMAP.md`、`app/CODEMAP.md`、`tests/CODEMAP.md` 的导航规则。

### 显式排除的参考

- `docs/project_or_workflow/2026-04-11-fire-qa-system-2.0-implementation-part-3.md`：**不作为本次执行参考**（历史实施记录，口径已过期）。

### 文档口径差异与裁决记录（实施前确认）

- **设计文档 L168「已知限制」** 写明：`received` 已发出后的持久化链路中若会话被删除，「第一版按 `internal_error` 处理，不做精确归因」。而 PRD L150 对 `conversation_not_found` 的语义描述可能被误读为「流中任意位置会话删除都能归因」。本计划以 PRD 测试决策 L186（『`received` 前』限定）与设计文档「已知限制」取交集裁决：**`conversation_not_found` 仅覆盖 `received` 发出前的会话删除；`received` 之后出现的 `ConversationNotFoundError` 仍归 `internal_error`**。实现手段：API 事件生成器跟踪 `received` 是否已发出（见步骤 2）。此裁决与两文档均不冲突，无需改文档。
- **裁决 1（已裁决）**：一次性接口 `POST /messages` 对 `PersistenceError` **不补** HTTP 映射（沿用现状「未捕获异常 → 500」）。该接口无前端流量，用户端细粒度文案动机仅由 stream 承担；未来若重新获得真实调用方再裁决。
- **裁决 2（已裁决）**：前端 `conversation_not_found` 分支的状态行文案定稿为「会话已失效，已返回首页。」（不承诺输入保留）。
- **裁决 3（已裁决）**：竞态场景由 E2E mock 确定性构造（`page.route` 伪造 stream 事件序列，见步骤 5），不再依赖手工复现真实时序；后端事件契约仍由步骤 1 API 集成测试锁定。

## 三、分批实施总览

- **第一批 = 需求 1 + 需求 2**：前端 404 识别 + 后端 `conversation_not_found` 分支 + 前端竞态分支行为。两者共享「前端开始看 HTTP 状态码 / error.code」能力，合并交付。
- **第二批 = 需求 3**：repository 薄封装（`PersistenceError` + 分型函数）→ 服务层异常包装（仅 4 个写方法 + 快照守卫）→ API 映射 → 前端固有档状态行。

## 四、实施步骤

### 第一批步骤（需求 1 + 需求 2）

---

#### 步骤 1：后端 API 集成测试先行——`conversation_not_found` 与「已知限制」边界

- **测试文件**：`tests/integration/api/test_conversations_api.py`（追加，不改既有用例）。
- **新增 fake（类级，置于 `FailingConversationTurnService` 之后）**：
  - `RaceDeleteBeforeReceivedTurnService`：`handle_user_message_stream` 不 yield 任何事件直接 `raise ConversationNotFoundError("conv-1")`（需 `from app.services.conversation_repository import ConversationNotFoundError`）。
  - `RaceDeleteAfterReceivedTurnService`：先 yield `received` 事件，随后 `raise ConversationNotFoundError(...)`。
- **断言要点**：
  - 前 received 删除：仅 1 行 error 事件；`code == "conversation_not_found"`；`message == "会话不存在或已删除"`；`retryable is False`。
  - 后 received 删除（对应设计文档「已知限制」）：`received` 行之后 error 事件 `code == "internal_error"`（显式锁定第一版不做精确归因）。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -k "conversation_not_found or race_after_received" -q
```

- **预期输出**：新增 2 个用例 FAILED（实现未落地，`code` 断言不通过或事件行数不符）；既有用例不受影响。
- **风险**：低。仅追加测试。

---

#### 步骤 2：后端实现——`event_generator` 增加 `ConversationNotFoundError` 分支（含 received 边界）

- **实现文件**：`app/api/conversations.py` 函数 `send_message_stream` 内部的 `event_generator`（:185-204）。
- **实现要点**：
  - 在 `for event in ...` 循环内跟踪 `received` 是否已 yield（如 `received_sent = False`，遇到 `event.type == "received"` 置 True）。
  - 在 `except ChatCompletionError` 之后、`except Exception` 之前插入 `except ConversationNotFoundError`：
    - `received_sent is False` → error 事件 `code="conversation_not_found"`、`message=MISSING_CONVERSATION_DETAIL`（复用 :31 常量）、`retryable=False`。
    - `received_sent is True` → 按「已知限制」发 `internal_error`（文案、retryable 与现有兜底一致）。
  - 不改动 `ChatCompletionError→model_error`、`except Exception→internal_error` 既有分支语义。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -q
```

- **预期输出**：步骤 1 新增 2 个用例 PASS，该文件全部用例 PASS。
- **依赖**：步骤 1。
- **风险**：低。分支顺序须保证 `ConversationNotFoundError`（`ValueError` 子类）在泛 `Exception` 前捕获。

---

#### 步骤 3：前端「错误对象开始携带 status / code / retryable」能力（需求 1、2、3 共享基座）

- **测试方式说明**：前端行为验收由 Playwright E2E 承担（用例见步骤 5），本步骤的 `node --check` 仅作语法冒烟。
- **实现文件**：`app/static/app.js`。
- **实现要点（三处小改动）**：
  1. `requestJson`（:117-140）`!response.ok` 分支：构造 `Error` 后挂载 `error.status = response.status` 再抛出。
  2. `fetchStreamMessage`（:640-657）非 ok 分支：同样挂载 `error.status = response.status`（让预检 404/503 也带状态，供后续分支复用）。
  3. `handleStreamEvent`（:704-707）`event.type === "error"` 分支：构造 `Error(event.message || ...)` 后挂载 `error.code = event.code || "internal_error"`、`error.retryable = Boolean(event.retryable)` 再抛出。
- **验证命令（语法冒烟）**：

```bash
node --check app/static/app.js
```

- **预期输出**：无输出退出码 0（node 仅做语法校验，不引入依赖）。
- **风险**：低。纯 Error 对象附加属性，不改变既有 catch 行为。

---

#### 步骤 4：前端需求 1（404 文案区分）+ 需求 2（conversation_not_found 分支）

- **实现文件**：`app/static/app.js`。
- **实现要点**：
  1. `openConversation` catch 分支（:467-477）改为状态区分：
     - `error.status === 404` → `showError("会话不存在或已删除")`；
     - 否则 → `showError(error.message || "读取会话失败。")`（现状逻辑，不得出现「不存在或已删除」字样）；
     - 其余回首页、清 active 状态、替换 URL 的既有行为不变。
  2. `sendMessage` catch 分支（:630-634）在现有兜底前增加 `conversation_not_found` 专属分支：
     - `showError(error.message)`；
     - `state.activeConversationId = null; state.activeDetail = null; setView("home"); updateUrl(null, { replace: true }); renderConversationList(); renderThread(); await loadConversationList();`（复用 `deleteConversation` wasActive 分支 :543-550 的既有样板）；
     - 不调用 `replacePendingAssistantWithError`（activeDetail 已置空）；
     - 不调用 `clearComposerValues`（保留输入框草稿）；
     - `setStatus` 文案（已裁决）：「会话已失效，已返回首页。」
- **验证命令**：

```bash
node --check app/static/app.js
```

- **预期输出**：语法通过。
- **E2E 用例**：见步骤 5（需求 1、需求 2 行为层均由 E2E 断言）。
- **依赖**：步骤 3。
- **风险**：中。`sendMessage` 捕获分支顺序须先判 `conversation_not_found` 再落入原兜底；`updateUrl(null, { replace: true })` 与 openConversation 失败分支的 replace 语义保持一致。

---

#### 步骤 5：第一批 E2E 测试——前端 404 区分与竞态删除分支

- **测试文件**：`tests/e2e/test_conversation_error_flows.py`（新建；沿用 pytest-playwright fixture）。
- **mock 方式**：`page.route` 拦截 `/api/conversations*`，按用例伪造响应；stream 接口返回可控 NDJSON（带 `Content-Type: application/x-ndjson`，行尾含换行），detail/列表接口返回可控 JSON 与状态码；全程不依赖真实模型/索引。
- **用例与断言要点**：
  1. 需求 1-404：GET detail 返回 404 → 错误面板显示「会话不存在或已删除」，回到首页；
  2. 需求 1-非404：GET detail 返回 500 → 文案不含「不存在或已删除」；
  3. 需求 2-主用例：stream 返回单行 `{"type":"error","code":"conversation_not_found","message":"会话不存在或已删除","retryable":false}` → 错误面板文案正确、`page.url` 回 `/`、会话列表不含该项、输入框草稿保留；
  4. 需求 2-边界（received 后）：stream 返回 `received` 行 + `internal_error` 行 → 页面不回首页，通用错误文案。
- **验证命令**：

```bash
conda run -n fire pytest tests/e2e -q
```

- **预期输出**：4 个用例 PASS（先于步骤 3/4 实现时为 FAILED，符合 TDD）。
- **风险**：中。NDJSON mock 需注意结尾换行与响应头；选择器依赖现有 `data-testid`。

---

#### 步骤 6：第一批提交（需用户显式授权后执行）

- **拟提交信息（中文）**：`第一批：会话404读取文案区分与流中会话删除conversation_not_found分支`
- **拟包含文件**：`app/api/conversations.py`、`app/static/app.js`、`tests/integration/api/test_conversations_api.py`、`tests/e2e/test_conversation_error_flows.py`。
- **回退预案**：见「八、回滚策略」。
- **风险**：低。

---

### 第二批步骤（需求 3）

---

#### 步骤 7：单元测试先行——repository 异常分型函数

- **测试文件**：`tests/unit/services/test_conversation_repository.py`（追加）。
- **断言要点**（针对拟新增公开函数 `to_persistence_error` 与异常类 `PersistenceError`）：
  - `sqlite3.OperationalError("database is locked")` → `PersistenceError`、`transient is True`；
  - 其他 `sqlite3.Error`（如 `sqlite3.IntegrityError`）→ `PersistenceError`、`transient is False`；
  - `RuntimeError` → `PersistenceError`、`transient is False`（快照守卫归固有档）；
  - 其余异常（如 `ValueError`、`ConversationNotFoundError`）→ 原样返回，不转换。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q
```

- **预期输出**：新增用例 FAILED（`PersistenceError` 未定义）；既有用例不受影响。
- **风险**：低。

---

#### 步骤 8：repository 薄封装——`PersistenceError` 与 `to_persistence_error`

- **实现文件**：`app/services/conversation_repository.py`（在 `ConversationNotFoundError` 定义 :67-68 之后追加）。
- **实现要点**：
  - `class PersistenceError(Exception)`：构造接收 `transient: bool` 关键字并保留 `__cause__` 链；
  - `def to_persistence_error(exc: Exception) -> Exception`：分型规则与《工程技术标准》L66 一致——仅 locked 类 `OperationalError`（`"locked" in str(exc).lower()`）瞬时；其余 `sqlite3.Error` 与 `RuntimeError` 固有；其他异常原样返回；
  - 不改动任何既有 SQL/写方法本体（薄封装，分型由调用方触发）。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q
```

- **预期输出**：全部 PASS。
- **依赖**：步骤 7。
- **风险**：低。

---

#### 步骤 9：单元测试先行——turn_service 仅包装 received 后 4 个写方法与快照守卫

- **测试文件**：`tests/unit/services/test_conversation_turn_service.py`（追加）。
- **测试构造方式**：沿用该文件既有 fake retriever/chat client 样板，repository 用真实 `ConversationRepository(tmp_path / "conversations.db")`（该文件现有用例同构），用 `monkeypatch.setattr` 替换单个写方法制造故障。
- **断言要点**：
  1. monkeypatch `repository.create_turn` 抛出 `sqlite3.OperationalError("database is locked")` → 迭代流在发出 `received` 后抛 `PersistenceError`、`transient is True`；
  2. monkeypatch `repository.save_answer_snapshot` 返回伪造的 `StoredAnswerSnapshot`（`turn_id` 与实际 turn 不一致）触发现有 :123-124 守卫 → 抛 `PersistenceError`、`transient is False`（快照守卫 RuntimeError 归固有档）；
  3. monkeypatch `repository.get_conversation_detail` 或首个 `append_message`（received 前）抛出 `sqlite3.Error` → 异常**原样传播**，不得被转为 `PersistenceError`（received 前失败仍归 `internal_error` 的测试锚点）；
  4. 正常路径回归：事件序列 `received→retrieving→generating→organizing_evidence→completed` 不受影响。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/unit/services/test_conversation_turn_service.py -q
```

- **预期输出**：新增 3 个故障用例 FAILED；既有用例 PASS。
- **依赖**：步骤 8（测试 importing `PersistenceError`）。
- **风险**：中。monkeypatch 需精确替换实例方法，注意 `create_turn` 的关键字参数签名。

---

#### 步骤 10：turn_service 异常包装实现

- **实现文件**：`app/services/conversation_turn_service.py`。
- **实现要点**：
  - 头部 `from app.services.conversation_repository import PersistenceError, to_persistence_error`；
  - 新增私有方法 `_persist(self, fn)`：`try: return fn() except Exception as exc: raise to_persistence_error(exc) from exc`；
  - 仅包装 `handle_user_message_stream` 中 `received` yield 之后的 4 个存储调用：`append_message(role="assistant")`（:81-85）、`create_turn`（:87-96）、`save_answer_snapshot`（:97-102）、`save_history_summary`（:113），以及快照守卫（:123-124 的 `raise RuntimeError` 移入包装路径：守卫比较在 `_persist` 内执行）；
  - 不包装 received 前的 `get_conversation_detail`（:50）、首个 `append_message`（:54）、`note_first_user_message`（:56）；
  - `handle_user_message`（一次性接口复用流）无需单独改动（其本就消费同一生成器）。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/unit/services/test_conversation_turn_service.py -q
```

- **预期输出**：全部 PASS。
- **依赖**：步骤 9。
- **风险**：中。守卫移入包装路径时保持「`snapshot.turn_id != turn.id` → 抛 RuntimeError」语义不变。

---

#### 步骤 11：API 集成测试先行——persistence_error 两档 + internal_error 锚点

- **测试文件**：`tests/integration/api/test_conversations_api.py`（追加）。
- **新增 fake**：
  - `PersistenceTransientTurnService`：yield `received` 后 `raise PersistenceError(transient=True)`；
  - `PersistencePermanentTurnService`：yield `received` 后 `raise PersistenceError(transient=False)`；
  - `FailingInternalTurnService`：不 yield 直接 `raise RuntimeError("db down")`（锁定 `internal_error` 兜底锚点）。
- **断言要点**：
  - 瞬时档：`code == "persistence_error"`、`message == "服务内部异常，请稍后重试。"`、`retryable is True`；
  - 固有档：`code == "persistence_error"`、`message == "回答无法保存，可能需要管理员检查系统存储或服务状态"`、`retryable is False`；
  - 锚点：generic RuntimeError → `code == "internal_error"`。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -k "persistence_error or internal" -q
```

- **预期输出**：新增用例 FAILED；既有用例 PASS。
- **依赖**：步骤 10（`PersistenceError` 已存在）。
- **风险**：低。

---

#### 步骤 12：API 映射——`event_generator` 增加 `PersistenceError` 分支

- **实现文件**：`app/api/conversations.py` `event_generator`。
- **实现要点**：
  - 头部 `from app.services.conversation_repository import PersistenceError`（与既有 import 合并）；
  - 在 `except ConversationNotFoundError` 之后、`except Exception` 之前插入 `except PersistenceError as exc`：
    - `exc.transient` → `message="服务内部异常，请稍后重试。"`、`retryable=True`；
    - 否则 → `message="回答无法保存，可能需要管理员检查系统存储或服务状态"`、`retryable=False`；
    - `code` 均为 `"persistence_error"`。
- **验证命令**：

```bash
conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -q
```

- **预期输出**：该文件全部 PASS。
- **依赖**：步骤 11。
- **风险**：低。

---

#### 步骤 13：前端固有档状态行

- **实现文件**：`app/static/app.js` `sendMessage` catch 分支（:630-634）。
- **实现要点**：在 `conversation_not_found` 分支之后、原兜底之前插入：
  - `error.code === "persistence_error" && error.retryable === false` → `showError(messageText); replacePendingAssistantWithError(messageText); setStatus("重试也无法恢复本轮回答。")`；
  - 其余错误（含瞬时档 persistence_error、model_error、internal_error、断网）保持现文案「…重试将产生新的提问」。
- **验证命令**：

```bash
node --check app/static/app.js
```

```bash
conda run -n fire pytest tests/e2e -q
```

- **预期输出**：语法通过；E2E 全部 PASS。
- **E2E 断言**：新增用例——stream mock 返回 `{"type":"error","code":"persistence_error","message":"回答无法保存，可能需要管理员检查系统存储或服务状态","retryable":false}` → 状态行为「重试也无法恢复本轮回答。」且不包含「重试将产生新的提问」；并补一个瞬时档对照用例（retryable=true → 状态行保持「…重试将产生新的提问」）。
- **依赖**：步骤 3 的 code/retryable 携带能力。
- **风险**：低。

---

#### 步骤 14：全量回归 + 全量验收清单核对

- **命令**：

```bash
conda run -n fire python -m pytest tests -q
```

- **预期输出**：全部 PASS；失败仅允许出现在与本 feature 明确无关、且与 `main` 基线一致的既有 flaky（若有，须逐条登记）。
- **动作**：对照「五、全量验收清单」逐条勾验。
- **风险**：低。

---

#### 步骤 15：文档收尾

- **实现文件**：`app/CODEMAP.md`。
- **要点**：`api/conversations.py` 行的 Function 描述补充错误事件分支现况（`model_error`/`internal_error`/`conversation_not_found`/`persistence_error` 四 code 及 received 边界）；`services/` 描述可补 `PersistenceError` 分型行（最小改动，不重生成全图）。
- **附带核对**：工程技术标准与 NDJSON 设计文档**无需改动**（两文档口径已在前序 commit 更新，本计划与之一致）；发现并登记任何出入。
- **风险**：低。

---

#### 步骤 16：第二批提交（需用户显式授权后执行）

- **拟提交信息（中文）**：`第二批：persistence_error瞬时/固有两档分型与前端固有档状态行`
- **拟包含文件**：`app/services/conversation_repository.py`、`app/services/conversation_turn_service.py`、`app/api/conversations.py`、`app/static/app.js`、`tests/unit/services/test_conversation_repository.py`、`tests/unit/services/test_conversation_turn_service.py`、`tests/integration/api/test_conversations_api.py`、`app/CODEMAP.md`（文档收尾并入本批）。
- **风险**：低。

---

## 五、全量验收清单

### 映射 PRD《测试决策》新增 3 条（L185-L187）

| PRD 验收条 | 对应自动化用例 | 前端行为层 E2E 用例 |
|---|---|---|
| L185：HTTP 404 打开已删会话显示「会话不存在或已删除」；mock 500/断网文案不含「不存在或已删除」 | 无后端用例（前端行为） | 步骤 5 E2E 用例 1、2 |
| L186：流中（received 前）会话被删 → 显示该文案、回 `/`、刷新列表、保留草稿，且 code ≠ internal_error | 步骤 1：`test_...conversation_not_found`（code/message/retryable）+ `test_...race_after_received`（internal_error 锁边界） | 步骤 5 E2E 用例 3（回 `/`、列表、草稿）；边界为用例 4 |
| L187：瞬时档用「服务内部异常，请稍后重试。」；固有档与快照守卫用「回答无法保存…」；固有档状态行不出现「重试将产生新的提问」；received 前落库失败仍为 internal_error | 步骤 7（分型）、步骤 9（transient/guard/pre-received 三锚点）、步骤 11（两档 API 事件 + internal_error 锚点） | 步骤 13 两个状态行用例（固有档 + 瞬时档对照） |

### 映射设计文档验证清单（四 code + 两档）

| 设计文档检查项 | 状态 / 用例 |
|---|---|
| `model_error` 流中错误事件 | 既有用例 `test_send_message_stream_returns_error_event_on_failure`（回归） |
| `internal_error` 泛兜底锚点 | 步骤 11 新增 `FailingInternalTurnService` 用例 |
| `conversation_not_found`（pre-received） | 步骤 1 新增用例 |
| `persistence_error` 瞬时档 | 步骤 11 新增用例 |
| `persistence_error` 固有档 | 步骤 11 新增用例 |
| 「已知限制」：received 后会话删除仍 internal_error | 步骤 1 `race_after_received` 用例 |
| 服务层事件顺序回归 | 既有 `test_conversation_turn_service.py` 用例 + 步骤 9 回归主张 |
| 响应头 / NDJSON 行完整回归 | 既有 `test_send_message_stream_returns_ndjson` |

## 六、文档收尾清单

1. `app/CODEMAP.md`：`api/conversations.py` 行更新错误分支描述（四 code + received 边界）；`services/` 补 `PersistenceError` 分型说明。
2. 确认《工程技术标准》L65-L66、NDJSON 设计文档 L159-L168 与实现一致（无需修改；如不一致登记差异）。
3. 本计划执行结束后，`implementation.md` 保留于仓库根作为执行记录，已单独提交入库。

## 七、提交策略（执行前逐批取得用户显式授权）

- **提交 1（第一批）**：`第一批：会话404读取文案区分与流中会话删除conversation_not_found分支`（步骤 1-5 的文件集）。前置检查：`git status` / `git diff` 仅含计划内三个代码/测试文件。
- **提交 2（第二批，含文档收尾）**：`第二批：persistence_error瞬时/固有两档分型与前端固有档状态行`。文档收尾（`app/CODEMAP.md`）并入本提交；若用户要求文档单独提交，则拆为提交 3：`文档：更新app CODEMAP错误分支与持久化分型描述`。
- 每批提交前执行该批全部验证命令；任何失败不提交。
- 本计划本身（`implementation.md`）单独提交（不并入两批 feature 提交）；执行过程中的计划修订随对应批次一并提交。

## 八、回滚策略

- **第一批回滚**：`git revert <提交1哈希>`（历史不改写）；若尚未提交，仅 `git restore` 计划内文件。回滚后重跑 `tests/integration/api/test_conversations_api.py` 应回到基线。
- **第二批回滚**：先 `git revert <提交2哈希>`；第二批依赖第一批的 `event_generator` 结构（except 插入顺序），故若两批均需回滚，按逆序 revert（先 2 后 1）。
- **部分失败回滚**：单步骤验证失败时不提交该批；回滚后重跑 `conda run -n fire pytest tests/e2e -q` 确认前端行为恢复（必要时辅以手工抽查）。
- 禁止用 `git reset`/`git checkout` 改写历史的方式回滚；一律走 `git revert`/`git restore`。

## 九、质量与风险备注

- 步骤粒度：每步「测试→实现→验证命令」闭环；命令块均为单条命令。
- PRD 与计划冲突时以 PRD 为准；已登记的口径差异见「二、文档口径差异与裁决记录」。
- 已确认的环境事实：Playwright 三件套已安装可用（用户已授权；playwright、Chromium、pytest-playwright 均按《工程技术标准》就绪），前端行为验收由 Playwright E2E 承担。
- 裁决清单（均已裁决）：①一次性 `/messages` 接口**不补** `PersistenceError` HTTP 映射（该接口无前端流量，用户端细粒度文案动机仅由 stream 承担；未来若重新获得真实调用方再裁决）；②`conversation_not_found` 前端状态行定稿「会话已失效，已返回首页。」（不承诺输入保留）；③`received` 前竞态场景由 E2E mock 确定性构造（`page.route` 伪造 stream 事件序列，见步骤 5），后端事件契约仍由步骤 1 API 集成测试锁定。
- **产品裁决候选（两批代码审查沉淀，待产品拍板，不阻塞本 feature）**：
  1. 直接访问/刷新失效会话 URL 时，视图回首页但地址栏被 `bootstrap()` 的 `updateUrl` 写回失效路径（`bootstrap` 在 `openConversation` 失败后无条件覆盖回首页 URL）——是否要求 404 后地址栏也回 `/`；
  2. 预检 HTTP 404（流开始前会话已删）目前走通用兜底（留在失效页、状态行提示重试），与流中 `conversation_not_found` 的四动作处理不一致——是否让 `error?.status === 404` 也触发回首页分支；
  3. error 事件各分支服务端无日志留痕（固有档引导"管理员检查系统存储"但管理员无诊断线索）——建议后续批次为各 except 分支补 `logger.exception`。
