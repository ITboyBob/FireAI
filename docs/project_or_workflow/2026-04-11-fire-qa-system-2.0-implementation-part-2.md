# 消防问答系统 2.0 实施计划（分卷二）

> 本文为实施计划分卷二；分卷导航见[实施计划总览](./2026-04-11-fire-qa-system-2.0-implementation.md)。

### Task 6: 定义 2.0 对话响应模型并实现修正提示策略

**Files:**
- Create: `app/schemas/conversation.py`
- Create: `app/services/conversation_presenter.py`
- Create: `tests/unit/services/test_conversation_presenter.py`

**Step 1: Write the failing test**

```python
from app.services.conversation_presenter import ConversationPresenter


def test_presenter_switches_to_new_clause_text_when_basis_changes():
    presenter = ConversationPresenter()
    previous_snapshot = {
        "legal_basis": ["《中华人民共和国消防法》第二条"],
        "clause_texts": [{"path": "旧路径", "text": "旧条文原文"}],
    }
    current_answer = {
        "conclusion": "河北省另有补充规定。",
        "citations": ["《河北省消防条例》第二十八条"],
        "evidence": [{"path": "新路径", "text": "新条文原文"}],
    }

    payload = presenter.build(
        answer=current_answer,
        previous_snapshot=previous_snapshot,
        is_followup=True,
    )

    assert payload.legal_basis == ["《河北省消防条例》第二十八条"]
    assert payload.clause_texts == [{"path": "新路径", "text": "新条文原文"}]
    assert payload.correction_notice == "本轮已根据最新检索证据修正前文。"
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_presenter.py -q`  
Expected: FAIL。

**Step 3: Write minimal implementation**

```python
class ConversationPresenter:
    CORRECTION_NOTICE = "本轮已根据最新检索证据修正前文。"

    def build(self, *, answer: dict, previous_snapshot: dict | None, is_followup: bool):
        legal_basis = answer.get("citations", [])
        current_clause_texts = [
            {"path": item["path"], "text": item["text"]}
            for item in answer.get("evidence", [])
        ]

        if is_followup and previous_snapshot and previous_snapshot.get("legal_basis") == legal_basis:
            clause_texts = previous_snapshot.get("clause_texts", current_clause_texts)
            correction_notice = ""
        elif is_followup and previous_snapshot:
            clause_texts = current_clause_texts
            correction_notice = self.CORRECTION_NOTICE
        else:
            clause_texts = current_clause_texts
            correction_notice = ""

        return {
            "answer": answer["conclusion"],
            "legal_basis": legal_basis,
            "clause_texts": clause_texts,
            "correction_notice": correction_notice,
        }
```

同一任务中，把 2.0 所需的 Pydantic schema 固定下来，至少包括：

- 会话列表项
- 会话详情
- 用户消息输入
- 助手消息展示结构
- 对话发送响应结构

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_presenter.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- “回答 + 法律依据 + 条款原文 + 修正提示”的用户侧展示模型已经稳定。
- 追问时优先复用上一轮条款原文、依据变化时切换为本轮条款原文的规则已落地。

### Task 7: 实现对话执行编排层

**Files:**
- Create: `app/services/conversation_turn_service.py`
- Modify: `app/services/query_normalizer.py`
- Modify: `tests/unit/services/test_query_normalizer.py`
- Create: `tests/unit/services/test_conversation_turn_service.py`

**Step 1: Write the failing test**

```python
from app.services.conversation_turn_service import ConversationTurnService


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query: str, *, top_k: int):
        self.calls.append((query, top_k))
        return [
            {
                "chunk_id": "xiaofangfa_2019#article-2",
                "document_id": "xiaofangfa_2019",
                "title": "中华人民共和国消防法",
                "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
                "text": "国家实行消防安全责任制。",
                "article_no": "第二条",
            }
        ]


def test_handle_user_message_requeries_with_context_hints(tmp_path):
    service = ConversationTurnService(...)
    result = service.handle_user_message("conv-1", "它第二条怎么说？")

    assert result.assistant.legal_basis == ["《中华人民共和国消防法》第二条"]
    assert "中华人民共和国消防法" in service.retriever.calls[0][0]
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_conversation_turn_service.py -q`  
Expected: FAIL，因为 `ConversationTurnService` 不存在，`query_normalizer` 也还不支持上下文提示。

**Step 3: Write minimal implementation**

```python
def normalize_query(question: str, *, context_hints: dict | None = None) -> str:
    hints = []
    if context_hints:
        canonical_title = context_hints.get("canonical_title")
        article_no = context_hints.get("article_no")
        if canonical_title:
            hints.append(canonical_title)
        if article_no:
            hints.append(article_no)
    return " ".join([*hints, question]).strip()


class ConversationTurnService:
    def handle_user_message(self, conversation_id: str, message: str):
        ...
        classification = self.turn_classifier.classify(message, previous_turns=previous_turns)
        query = normalize_query(message, context_hints=classification["context_hints"])
        evidence = self.retriever.search(query, top_k=5)
        answer = build_answer(evidence, client=self.chat_client, question=message)
        assistant_payload = self.presenter.build(...)
        ...
```

同一任务中补齐：

- 首条用户消息触发自动标题
- 保存 `rewritten_query`
- 保存 `history_summary_used`
- 保存 `knowledge_version`
- 在摘要不可用时自动降级

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_conversation_turn_service.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 从“用户消息 -> 追问判定 -> 上下文组装 -> 重检索 -> 回答 -> 快照落库”的应用层主链已经存在。
- 多轮能力没有绕过检索，仍然以本轮最新证据为准。

### Task 8: 暴露会话管理与消息执行 API

**Files:**
- Create: `app/api/conversations.py`
- Create: `tests/integration/api/test_conversations_api.py`
- Create: `tests/unit/api/test_conversation_dependencies.py`
- Modify: `app/main.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.api.conversations import get_conversation_service, get_conversation_turn_service
from app.main import create_app


class FakeConversationService:
    def __init__(self):
        self.conversation = {"id": "conv-1", "title": "新会话"}

    def create_conversation(self):
        return self.conversation


class FakeConversationTurnService:
    def handle_user_message(self, conversation_id: str, message: str):
        assert conversation_id == "conv-1"
        assert message == "消防法第二条怎么说？"
        return {
            "assistant": {
                "message_id": "msg-2",
                "answer": "国家实行消防安全责任制。",
                "legal_basis": ["《中华人民共和国消防法》第二条"],
                "clause_texts": [
                    {"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}
                ],
                "correction_notice": "",
                "created_at": "2026-04-11T10:00:00Z",
            }
        }


def test_create_conversation_then_send_message_returns_assistant_payload():
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    app.dependency_overrides[get_conversation_turn_service] = lambda: FakeConversationTurnService()
    client = TestClient(app)

    created = client.post("/api/conversations", json={})
    conversation_id = created.json()["id"]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "消防法第二条怎么说？"},
    )

    assert created.status_code == 201
    assert response.status_code == 200
    assert set(response.json()["assistant"].keys()) == {
        "message_id",
        "answer",
        "legal_basis",
        "clause_texts",
        "correction_notice",
        "created_at",
    }
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/unit/api/test_conversation_dependencies.py -q`  
Expected: FAIL，因为新路由和依赖还不存在。

**Step 3: Write minimal implementation**

```python
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", status_code=201)
async def create_conversation(...): ...


@router.get("")
async def list_conversations(...): ...


@router.get("/{conversation_id}")
async def get_conversation_detail(...): ...


@router.patch("/{conversation_id}")
async def rename_conversation(...): ...


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(...): ...


@router.post("/{conversation_id}/messages")
async def send_message(...): ...
```

在 `app/main.py` 中完成：

- 注册新 router
- 保留现有 `/api/chat` 路由不动，作为兼容回归入口

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/unit/api/test_conversation_dependencies.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 系统已经提供正式的会话管理 API 和消息执行 API。
- 前端不再必须依赖单一 `/api/chat` 才能工作。

### Task 9: 切换网页壳到双栏会话界面

**Files:**
- Modify: `app/templates/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`
- Modify: `tests/integration/api/test_chat_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_root_page_renders_conversation_shell():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="conversation-list"' in response.text
    assert 'id="conversation-thread"' in response.text
    assert 'id="composer-form"' in response.text
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q`  
Expected: FAIL，因为根页面还是旧的极薄单轮面板。

**Step 3: Write minimal implementation**

```html
<aside class="conversation-sidebar">
  <button id="new-conversation-button" type="button">新建会话</button>
  <ul id="conversation-list"></ul>
</aside>

<section class="conversation-main">
  <div id="conversation-thread"></div>
  <form id="composer-form"></form>
</section>
```

`app/static/app.js` 最小实现必须覆盖：

- 首次加载会话列表
- 新建会话
- 点击切换当前会话
- 提交问题
- 渲染用户消息
- 渲染助手回答、法律依据、条款原文、修正提示
- 重命名会话
- 删除会话

`app/static/app.css` 最小实现必须覆盖：

- 左右双栏布局
- 会话列表可滚动
- 当前会话消息区可滚动
- 条款原文块与修正提示有清晰视觉区分

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 根页面从“单轮验证面板”升级为“会话列表 + 当前会话”的双栏产品界面。
- 前端已改为使用 `/api/conversations/*` 作为主链路。

### Task 10: 更新文档并完成最终验证

**Files:**
- Modify: `README.md`
- Modify: `docs/system_meta/文档索引.md`

**Step 1: Write the failing documentation checklist**

```text
1. README 仍然把系统描述成“极薄聊天面板”
2. 文档索引还没有 2.0 实施计划入口
```

**Step 2: Run the affected tests before doc edits**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py tests/unit/services/test_conversation_turn_service.py tests/integration/api/test_conversations_api.py tests/integration/api/test_chat_api.py -q`  
Expected: PASS；若失败，先回到对应任务修复，不要带着红测改文档。

**Step 3: Write minimal documentation updates**

README 至少更新：

- 当前能力改为“消防问答系统 2.0”
- 新网页入口说明
- 会话管理能力说明
- `/api/conversations/*` 说明
- 已知限制改为“本机单用户、无会话搜索、无多用户”

`docs/system_meta/文档索引.md` 至少更新：

- 新增 2.0 实施计划入口
- 说明“产品目标看 PRD，2.0 代码推进看 2.0 实施计划”

**Step 4: Run the full verification suite**

先跑自动化测试：

```bash
conda run -n fire python -m pytest tests/unit/core/test_settings.py \
  tests/unit/services/test_conversation_repository.py \
  tests/unit/services/test_conversation_service.py \
  tests/unit/services/test_turn_classifier.py \
  tests/unit/services/test_context_manager.py \
  tests/unit/services/test_conversation_summary.py \
  tests/unit/services/test_knowledge_version.py \
  tests/unit/services/test_conversation_presenter.py \
  tests/unit/services/test_query_normalizer.py \
  tests/unit/services/test_conversation_turn_service.py \
  tests/unit/api/test_chat_dependencies.py \
  tests/unit/api/test_conversation_dependencies.py \
  tests/integration/api/test_chat_api.py \
  tests/integration/api/test_conversations_api.py -q
```

再跑全量回归：

```bash
conda run -n fire python -m pytest -q
```

再跑真实上游构建验证：

```bash
conda run -n fire python scripts/build_corpus.py
conda run -n fire python scripts/build_index.py
```

最后做真实手工验证：

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

手工检查项：

1. 打开 `/`，确认能看到会话列表和当前会话区。
2. 新建会话并发送问题“消防法关于消防安全责任制怎么规定？”。
3. 在同一会话继续追问“它第二条怎么说？”。
4. 重命名会话并删除一个无用会话。
5. 重启服务后重新打开页面，确认历史会话仍可见。
6. 在旧会话继续提问“河北也适用吗？”，确认系统仍走最新检索。
7. 若本轮法律依据变化，确认页面出现修正提示。

若 `.env` 中的 `CHAT_*` 仍是占位值，不得宣称真实多轮问答链路已验证通过；此时只能宣称结构、检索和持久化链路通过。

**Step 5: Record the completion checkpoint**

Expected state:

- README 和文档索引与 2.0 实现一致。
- 自动化测试通过。
- 真实上游构建与真实手工验证完成。
- 系统已经从单轮验证面板升级为可持续使用的本地会话问答产品。
