from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class StoredConversation:
    id: str
    title: str
    auto_title: bool
    created_at: str
    updated_at: str
    last_message_at: str | None
    deleted_at: str | None


@dataclass(frozen=True)
class StoredMessage:
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


@dataclass(frozen=True)
class StoredTurn:
    id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    is_followup: bool
    rewritten_query: str
    history_summary_used: str
    knowledge_version: str
    correction_notice: str
    created_at: str


@dataclass(frozen=True)
class StoredAnswerSnapshot:
    id: str
    turn_id: str
    answer: str
    legal_basis: list[str]
    clause_texts: list[dict[str, str]]
    created_at: str


@dataclass(frozen=True)
class ConversationDetail:
    conversation: StoredConversation
    messages: list[StoredMessage]
    turns: list[StoredTurn]
    snapshots: list[StoredAnswerSnapshot]


class ConversationNotFoundError(ValueError):
    """Raised when a conversation does not exist or has been soft-deleted."""


class ConversationRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_conversation(self, *, title: str, auto_title: bool) -> StoredConversation:
        timestamp = _utc_now()
        conversation = StoredConversation(
            id=str(uuid.uuid4()),
            title=title,
            auto_title=auto_title,
            created_at=timestamp,
            updated_at=timestamp,
            last_message_at=None,
            deleted_at=None,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    id,
                    title,
                    auto_title,
                    created_at,
                    updated_at,
                    last_message_at,
                    deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.id,
                    conversation.title,
                    int(conversation.auto_title),
                    conversation.created_at,
                    conversation.updated_at,
                    conversation.last_message_at,
                    conversation.deleted_at,
                ),
            )
        return conversation

    def append_message(self, conversation_id: str, *, role: str, content: str) -> StoredMessage:
        self._require_active_conversation(conversation_id)
        message = StoredMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=_utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.conversation_id,
                    message.role,
                    message.content,
                    message.created_at,
                ),
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = ?, last_message_at = ?
                WHERE id = ?
                """,
                (message.created_at, message.created_at, conversation_id),
            )
        return message

    def create_turn(
        self,
        *,
        conversation_id: str,
        user_message_id: str,
        assistant_message_id: str,
        is_followup: bool,
        rewritten_query: str,
        history_summary_used: str,
        knowledge_version: str,
        correction_notice: str,
    ) -> StoredTurn:
        self._require_active_conversation(conversation_id)
        turn = StoredTurn(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            is_followup=is_followup,
            rewritten_query=rewritten_query,
            history_summary_used=history_summary_used,
            knowledge_version=knowledge_version,
            correction_notice=correction_notice,
            created_at=_utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO turns (
                    id,
                    conversation_id,
                    user_message_id,
                    assistant_message_id,
                    is_followup,
                    rewritten_query,
                    history_summary_used,
                    knowledge_version,
                    correction_notice,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.id,
                    turn.conversation_id,
                    turn.user_message_id,
                    turn.assistant_message_id,
                    int(turn.is_followup),
                    turn.rewritten_query,
                    turn.history_summary_used,
                    turn.knowledge_version,
                    turn.correction_notice,
                    turn.created_at,
                ),
            )
        return turn

    def save_answer_snapshot(
        self,
        *,
        turn_id: str,
        answer: str,
        legal_basis: list[str],
        clause_texts: list[dict[str, str]],
    ) -> StoredAnswerSnapshot:
        snapshot = StoredAnswerSnapshot(
            id=str(uuid.uuid4()),
            turn_id=turn_id,
            answer=answer,
            legal_basis=legal_basis,
            clause_texts=clause_texts,
            created_at=_utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO answer_snapshots (
                    id,
                    turn_id,
                    answer,
                    legal_basis_json,
                    clause_texts_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.turn_id,
                    snapshot.answer,
                    json.dumps(snapshot.legal_basis, ensure_ascii=False),
                    json.dumps(snapshot.clause_texts, ensure_ascii=False),
                    snapshot.created_at,
                ),
            )
        return snapshot

    def get_conversation_detail(self, conversation_id: str) -> ConversationDetail:
        with self._connect() as connection:
            conversation_row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND deleted_at IS NULL",
                (conversation_id,),
            ).fetchone()
            if conversation_row is None:
                raise ConversationNotFoundError(conversation_id)

            message_rows = connection.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at, id
                """,
                (conversation_id,),
            ).fetchall()
            turn_rows = connection.execute(
                """
                SELECT * FROM turns
                WHERE conversation_id = ?
                ORDER BY created_at, id
                """,
                (conversation_id,),
            ).fetchall()
            snapshot_rows = connection.execute(
                """
                SELECT answer_snapshots.*
                FROM answer_snapshots
                JOIN turns ON turns.id = answer_snapshots.turn_id
                WHERE turns.conversation_id = ?
                ORDER BY turns.created_at, answer_snapshots.id
                """,
                (conversation_id,),
            ).fetchall()

        return ConversationDetail(
            conversation=self._build_conversation(conversation_row),
            messages=[self._build_message(row) for row in message_rows],
            turns=[self._build_turn(row) for row in turn_rows],
            snapshots=[self._build_snapshot(row) for row in snapshot_rows],
        )

    def update_conversation_title(self, conversation_id: str, *, title: str, auto_title: bool) -> StoredConversation:
        self._require_active_conversation(conversation_id)
        updated_at = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET title = ?, auto_title = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (title, int(auto_title), updated_at, conversation_id),
            )
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND deleted_at IS NULL",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(conversation_id)
        return self._build_conversation(row)

    def list_conversations(self) -> list[StoredConversation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversations
                WHERE deleted_at IS NULL
                ORDER BY last_message_at DESC, updated_at DESC, created_at DESC, id DESC
                """
            ).fetchall()
        return [self._build_conversation(row) for row in rows]

    def soft_delete_conversation(self, conversation_id: str) -> None:
        deleted_at = _utc_now()
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE conversations
                SET deleted_at = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (deleted_at, deleted_at, conversation_id),
            )
        if result.rowcount == 0:
            raise ConversationNotFoundError(conversation_id)

    def get_conversation(self, conversation_id: str) -> StoredConversation:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND deleted_at IS NULL",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(conversation_id)
        return self._build_conversation(row)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    auto_title INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_message_at TEXT,
                    deleted_at TEXT
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );

                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    user_message_id TEXT NOT NULL,
                    assistant_message_id TEXT NOT NULL,
                    is_followup INTEGER NOT NULL,
                    rewritten_query TEXT NOT NULL,
                    history_summary_used TEXT NOT NULL,
                    knowledge_version TEXT NOT NULL,
                    correction_notice TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                    FOREIGN KEY (user_message_id) REFERENCES messages(id),
                    FOREIGN KEY (assistant_message_id) REFERENCES messages(id)
                );

                CREATE TABLE IF NOT EXISTS answer_snapshots (
                    id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    legal_basis_json TEXT NOT NULL,
                    clause_texts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (turn_id) REFERENCES turns(id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _require_active_conversation(self, conversation_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM conversations WHERE id = ? AND deleted_at IS NULL",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(conversation_id)

    def _build_conversation(self, row: sqlite3.Row) -> StoredConversation:
        return StoredConversation(
            id=row["id"],
            title=row["title"],
            auto_title=bool(row["auto_title"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_message_at=row["last_message_at"],
            deleted_at=row["deleted_at"],
        )

    def _build_message(self, row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )

    def _build_turn(self, row: sqlite3.Row) -> StoredTurn:
        return StoredTurn(
            id=row["id"],
            conversation_id=row["conversation_id"],
            user_message_id=row["user_message_id"],
            assistant_message_id=row["assistant_message_id"],
            is_followup=bool(row["is_followup"]),
            rewritten_query=row["rewritten_query"],
            history_summary_used=row["history_summary_used"],
            knowledge_version=row["knowledge_version"],
            correction_notice=row["correction_notice"],
            created_at=row["created_at"],
        )

    def _build_snapshot(self, row: sqlite3.Row) -> StoredAnswerSnapshot:
        return StoredAnswerSnapshot(
            id=row["id"],
            turn_id=row["turn_id"],
            answer=row["answer"],
            legal_basis=list(json.loads(row["legal_basis_json"])),
            clause_texts=list(json.loads(row["clause_texts_json"])),
            created_at=row["created_at"],
        )
