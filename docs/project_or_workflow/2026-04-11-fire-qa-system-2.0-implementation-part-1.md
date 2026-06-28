# 消防问答系统 2.0 实施计划

> 本文为实施计划分卷一；分卷导航见[实施计划总览](./2026-04-11-fire-qa-system-2.0-implementation.md)。

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
- 流式状态专项的设计依据见 [消防问答 NDJSON 状态流设计](../architecture_or_strategy/2026-04-23-fire-qa-ndjson-status-stream-design.md)。统一命名为：**后端 NDJSON 状态流，最终可信结果由前端逐字呈现**。

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
