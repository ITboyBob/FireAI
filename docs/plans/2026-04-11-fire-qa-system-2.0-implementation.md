# 消防问答系统 2.0 实施计划

> 本计划可在当前工作区按批次执行。历史 `Task 1-10` 记录已完成的 2.0 会话主线；新增“流式状态专项阶段”记录后端 NDJSON 状态流与前端逐字呈现的后续实施步骤。

**目标：** 基于已批准的 PRD，把当前单轮消防法律 RAG 升级为具备本机持久化会话、历史恢复和多轮上下文管理的“消防问答系统 2.0”。

**架构：** 保留现有离线建库、查询规范化、混合检索和答案生成能力，把在线层升级为会话感知应用层。当前已新增本机 `SQLite` 会话存储、追问判定、上下文管理、历史摘要、回答快照和双栏网页壳；短期保留 `/api/chat` 作为兼容回归路径，前端正式流量切换到 `/api/conversations/*`。后续流式状态专项新增 `POST /api/conversations/{conversation_id}/messages/stream`，采用后端 NDJSON 状态流，最终可信结果由前端逐字呈现。

**技术栈：** Python 3.14、FastAPI、Pydantic、Python 标准库 `sqlite3`、Jinja2、原生 HTML/CSS/JS、pytest；若 `fire` 环境中 Playwright 可用，则用 Chromium 做关键路径 E2E。

---

## 计划说明

- 每次开始任务前，先查看本任务涉及库或工具的最新官方文档。若需要联网检索，只能使用 Firecrawl、Exa 或 Tavily。
- 严格遵守 TDD：先写失败测试，确认失败，再写最小实现，确认通过。
- 所有代码执行命令默认使用 `conda run -n fire ...`。
- 依赖情况：**无需新增依赖，沿用当前 `fire` 环境。** 本期持久化使用 Python 标准库 `sqlite3`。流式状态专项可先在 `fire` 环境确认 Playwright 是否可用；若不可用，只记录阻塞，不私自安装。
- 执行时优先参考：`@backend-patterns`、`@frontend-patterns`、`@python-testing`、`@tdd-workflow`。若出现异常行为，先按 `@systematic-debugging` 排查，再决定是否改代码。
- 本计划默认把“历史摘要”实现为**确定性摘要器**，从旧轮次的用户问题、法律依据和修正标记压缩出摘要，不额外引入新的 LLM 摘要调用。
- 流式状态专项的设计依据见 [消防问答 NDJSON 状态流设计](./2026-04-23-fire-qa-ndjson-status-stream-design.md)。统一命名为：**后端 NDJSON 状态流，最终可信结果由前端逐字呈现**。

### Task 1: 扩展本地会话配置

**Files:**
- Modify: `app/core/settings.py`
- Modify: `tests/unit/core/test_settings.py`
- Modify: `.env.example`

**Step 1: Write the failing test**

```python
from pathlib import Path

from app.core.settings import Settings


def test_settings_build_conversation_defaults():
    settings = Settings.model_validate({})
    assert settings.conversation_db_path == Path("var") / "conversations.db"
    assert settings.conversation_context_window_turns == 4
    assert settings.conversation_summary_trigger_turns == 6
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/core/test_settings.py -q`  
Expected: FAIL，因为 `Settings` 还没有 `conversation_db_path`、`conversation_context_window_turns` 或 `conversation_summary_trigger_turns`。

**Step 3: Write minimal implementation**

```python
from pathlib import Path


class Settings(BaseSettings):
    ...
    conversation_db_path: Path = Path("var") / "conversations.db"
    conversation_context_window_turns: int = 4
    conversation_summary_trigger_turns: int = 6
```

同时更新 `.env.example`，加入会话相关配置占位项，至少包括：

- `CONVERSATION_DB_PATH`
- `CONVERSATION_CONTEXT_WINDOW_TURNS`
- `CONVERSATION_SUMMARY_TRIGGER_TURNS`

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/core/test_settings.py -q`  
Expected: PASS，输出包含 `1 passed` 或更高通过数。

**Step 5: Record the completion checkpoint**

Expected state:

- 配置层已经能稳定提供本机会话数据库路径和上下文窗口参数。
- `Settings` 默认值不会把会话数据落到可重建的 `data/` 目录里。

### Task 2: 建立 SQLite 会话仓库

**Files:**
- Create: `app/services/conversation_repository.py`
- Create: `tests/unit/services/test_conversation_repository.py`
- Modify: `app/services/__init__.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from app.services.conversation_repository import ConversationRepository


def test_repository_round_trips_conversation_and_snapshot(tmp_path: Path):
    repo = ConversationRepository(tmp_path / "conversations.db")

    conversation = repo.create_conversation(title="新会话", auto_title=True)
    user_message = repo.append_message(conversation.id, role="user", content="消防法第二条是什么？")
    assistant_message = repo.append_message(conversation.id, role="assistant", content="国家实行消防安全责任制。")
    turn = repo.create_turn(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        is_followup=False,
        rewritten_query="消防法 第二条 消防法第二条是什么？",
        history_summary_used="",
        knowledge_version="kb:test",
        correction_notice="",
    )
    repo.save_answer_snapshot(
        turn_id=turn.id,
        answer="国家实行消防安全责任制。",
        legal_basis=["《中华人民共和国消防法》第二条"],
        clause_texts=[{"path": "中华人民共和国消防法 > 第一章 总则 > 第二条", "text": "国家实行消防安全责任制。"}],
    )

    detail = repo.get_conversation_detail(conversation.id)

    assert detail.conversation.id == conversation.id
    assert detail.messages[0].content == "消防法第二条是什么？"
    assert detail.snapshots[0].legal_basis == ["《中华人民共和国消防法》第二条"]
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q`  
Expected: FAIL，报 `ModuleNotFoundError` 或仓库接口不存在。

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import uuid


@dataclass(frozen=True)
class StoredConversation:
    id: str
    title: str
    auto_title: bool


class ConversationRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_conversation(self, *, title: str, auto_title: bool) -> StoredConversation:
        conversation_id = str(uuid.uuid4())
        ...
        return StoredConversation(id=conversation_id, title=title, auto_title=auto_title)
```

最小可用实现必须覆盖：

- 数据库文件父目录自动创建
- 表结构初始化
- `conversations`
- `messages`
- `turns`
- `answer_snapshots`
- 创建会话
- 追加消息
- 创建轮次
- 保存回答快照
- 读取会话详情

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q`  
Expected: PASS，输出 `1 passed` 或更多。

**Step 5: Record the completion checkpoint**

Expected state:

- 本地 `SQLite` 仓库已经能持久化会话、消息、轮次和回答快照。
- 数据库路径使用 `Settings.conversation_db_path` 指向的本机文件。

### Task 3: 实现会话服务与自动标题规则

**Files:**
- Create: `app/services/conversation_service.py`
- Create: `tests/unit/services/test_conversation_service.py`
- Modify: `app/services/conversation_repository.py`

**Step 1: Write the failing test**

```python
from app.services.conversation_repository import ConversationRepository
from app.services.conversation_service import ConversationService


def test_note_first_user_message_sets_auto_title(tmp_path):
    repo = ConversationRepository(tmp_path / "conversations.db")
    service = ConversationService(repository=repo)

    conversation = service.create_conversation()
    service.note_first_user_message(conversation.id, "消防法关于消防安全责任制怎么规定？")

    detail = service.get_conversation_detail(conversation.id)
    assert detail.conversation.title == "消防法关于消防安全责任制怎么规定"
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q`  
Expected: FAIL，报 `ModuleNotFoundError` 或 `ConversationService` 缺失。

**Step 3: Write minimal implementation**

```python
class ConversationService:
    def __init__(self, *, repository):
        self.repository = repository

    def create_conversation(self):
        return self.repository.create_conversation(title="新会话", auto_title=True)

    def note_first_user_message(self, conversation_id: str, message: str) -> None:
        title = message.strip().rstrip("？?。.!！")[:20] or "新会话"
        self.repository.update_conversation_title(conversation_id, title=title, auto_title=False)
```

同一任务中补齐以下行为：

- 列表按 `last_message_at` 倒序
- 会话重命名
- 会话软删除
- 已删除会话不可继续写入

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 新会话默认标题为“新会话”。
- 首条用户消息写入后，会自动生成更可读的标题。
- 会话的创建、重命名、删除和详情读取已稳定落在服务层。

### Task 4: 实现追问判定与上下文窗口管理

**Files:**
- Create: `app/services/turn_classifier.py`
- Create: `app/services/context_manager.py`
- Create: `tests/unit/services/test_turn_classifier.py`
- Create: `tests/unit/services/test_context_manager.py`

**Step 1: Write the failing test**

```python
from app.services.turn_classifier import TurnClassifier


def test_classify_followup_detects_pronoun_and_inherits_title():
    classifier = TurnClassifier()
    previous_turns = [
        {
            "question": "消防法关于消防安全责任制怎么规定？",
            "legal_basis": ["《中华人民共和国消防法》第二条"],
            "canonical_title": "中华人民共和国消防法",
            "article_no": "第二条",
        }
    ]

    result = classifier.classify("它第二条怎么说？", previous_turns=previous_turns)

    assert result.is_followup is True
    assert result.context_hints["canonical_title"] == "中华人民共和国消防法"
    assert result.context_hints["article_no"] == "第二条"
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py -q`  
Expected: FAIL，相关模块不存在。

**Step 3: Write minimal implementation**

```python
class TurnClassifier:
    FOLLOW_UP_MARKERS = ("它", "这个", "上一条", "上一轮", "继续", "那第二条")

    def classify(self, message: str, *, previous_turns: list[dict]) -> dict:
        if previous_turns and any(marker in message for marker in self.FOLLOW_UP_MARKERS):
            previous = previous_turns[-1]
            return {
                "is_followup": True,
                "context_hints": {
                    "canonical_title": previous.get("canonical_title", ""),
                    "article_no": previous.get("article_no", ""),
                },
            }
        return {"is_followup": False, "context_hints": {}}
```

`ContextManager` 最小实现必须覆盖：

- 只保留最近 `N` 轮
- 接收历史摘要
- 摘要缺失时降级为“仅最近 N 轮”

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 系统已经可以把“明显依赖前文”的输入识别成追问。
- 上下文输入不再是无限增长的全量历史，而是“最近 N 轮 + 更早摘要”。

### Task 5: 实现确定性历史摘要与知识库版本解析

**Files:**
- Create: `app/services/conversation_summary.py`
- Create: `app/services/knowledge_version.py`
- Create: `tests/unit/services/test_conversation_summary.py`
- Create: `tests/unit/services/test_knowledge_version.py`

**Step 1: Write the failing test**

```python
from app.services.conversation_summary import ConversationSummaryManager


def test_build_history_summary_compacts_older_turns():
    manager = ConversationSummaryManager()
    older_turns = [
        {
            "question": "消防法关于消防安全责任制怎么规定？",
            "legal_basis": ["《中华人民共和国消防法》第二条"],
            "correction_notice": "",
        },
        {
            "question": "河北也适用吗？",
            "legal_basis": ["《河北省消防条例》第二十八条"],
            "correction_notice": "本轮已根据最新检索证据修正前文。",
        },
    ]

    summary = manager.build_summary(older_turns)

    assert "中华人民共和国消防法" in summary
    assert "河北省消防条例" in summary
    assert "已修正前文" in summary
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py -q`  
Expected: FAIL。

**Step 3: Write minimal implementation**

```python
class ConversationSummaryManager:
    def build_summary(self, older_turns: list[dict]) -> str:
        lines = []
        for turn in older_turns:
            basis = "、".join(turn.get("legal_basis", [])) or "无明确依据"
            prefix = "修正：" if turn.get("correction_notice") else ""
            lines.append(f"{prefix}{turn['question']} -> {basis}")
        return "\n".join(lines)
```

`KnowledgeVersionResolver` 最小实现建议：

- 读取 `data/index/retrieval.db`
- 读取 `data/index/faiss.index`
- 读取 `data/index/vector_map.json`
- 组合文件名、大小和修改时间并生成稳定版本串

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py -q`  
Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 长会话已有可控的确定性摘要来源。
- 每轮回答都可以附带知识库版本标识，为后续排查提供依据。

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
- Modify: `docs/文档索引.md`

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

`docs/文档索引.md` 至少更新：

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

计划已保存至 `docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md`。
