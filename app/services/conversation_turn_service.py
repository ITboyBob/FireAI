from collections.abc import Mapping
import re
from typing import Any

from app.schemas.conversation import SendConversationMessageResponse
from app.services.answer_service import build_answer
from app.services.conversation_repository import ConversationDetail, ConversationRepository, StoredAnswerSnapshot
from app.services.conversation_service import ConversationService
from app.services.query_normalizer import normalize_query


CITATION_PATTERN = re.compile(r"《(?P<title>[^》]+)》(?P<article>第[^》]+条)?")


class ConversationTurnService:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        conversation_service: ConversationService,
        turn_classifier: Any,
        context_manager: Any,
        summary_manager: Any,
        knowledge_version_resolver: Any,
        retriever: Any,
        chat_client: Any,
        presenter: Any,
        summary_trigger_turns: int = 6,
        retrieval_top_k: int = 5,
    ):
        self.repository = repository
        self.conversation_service = conversation_service
        self.turn_classifier = turn_classifier
        self.context_manager = context_manager
        self.summary_manager = summary_manager
        self.knowledge_version_resolver = knowledge_version_resolver
        self.retriever = retriever
        self.chat_client = chat_client
        self.presenter = presenter
        self.summary_trigger_turns = summary_trigger_turns
        self.retrieval_top_k = retrieval_top_k

    def handle_user_message(self, conversation_id: str, message: str) -> SendConversationMessageResponse:
        detail = self.repository.get_conversation_detail(conversation_id)
        previous_turns = self._build_previous_turns(detail)
        previous_snapshot = detail.snapshots[-1] if detail.snapshots else None

        user_message = self.repository.append_message(conversation_id, role="user", content=message)
        if not detail.messages:
            self.conversation_service.note_first_user_message(conversation_id, message)

        classification = self.turn_classifier.classify(message, previous_turns=previous_turns)
        history_summary = self._build_history_summary(previous_turns)
        context = self.context_manager.build(previous_turns, history_summary=history_summary)
        normalized = normalize_query(message, context_hints=classification.context_hints)
        evidence = self.retriever.search(normalized, top_k=self.retrieval_top_k)
        answer = build_answer(evidence, client=self.chat_client, question=message)

        assistant_payload = self.presenter.build(
            answer=answer,
            previous_snapshot=previous_snapshot,
            is_followup=classification.is_followup,
        )
        assistant_message = self.repository.append_message(
            conversation_id,
            role="assistant",
            content=assistant_payload.answer,
        )
        knowledge_version = self.knowledge_version_resolver.resolve()
        turn = self.repository.create_turn(
            conversation_id=conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            is_followup=classification.is_followup,
            rewritten_query=normalized.rewritten_query,
            history_summary_used=context.history_summary,
            knowledge_version=knowledge_version,
            correction_notice=assistant_payload.correction_notice,
        )
        snapshot = self.repository.save_answer_snapshot(
            turn_id=turn.id,
            answer=assistant_payload.answer,
            legal_basis=assistant_payload.legal_basis,
            clause_texts=assistant_payload.clause_texts,
        )

        payload = self.presenter.build(
            answer=answer,
            previous_snapshot=previous_snapshot,
            is_followup=classification.is_followup,
            message_id=assistant_message.id,
            created_at=assistant_message.created_at,
        )

        if snapshot.turn_id != turn.id:
            raise RuntimeError("snapshot was not persisted for the created turn")
        return SendConversationMessageResponse(assistant=payload)

    def _build_history_summary(self, previous_turns: list[dict[str, Any]]) -> str:
        if len(previous_turns) < self.summary_trigger_turns:
            return ""

        recent_window = self.context_manager.window_turns
        older_turns = previous_turns[:-recent_window] if recent_window > 0 else previous_turns
        if not older_turns:
            return ""

        try:
            return self.summary_manager.build_summary(older_turns)
        except Exception:
            return ""

    def _build_previous_turns(self, detail: ConversationDetail) -> list[dict[str, Any]]:
        messages_by_id = {message.id: message for message in detail.messages}
        snapshots_by_turn_id = {snapshot.turn_id: snapshot for snapshot in detail.snapshots}

        previous_turns: list[dict[str, Any]] = []
        for turn in detail.turns:
            user_message = messages_by_id.get(turn.user_message_id)
            snapshot = snapshots_by_turn_id.get(turn.id)
            title, article_no = self._extract_citation_context(snapshot)
            previous_turns.append(
                {
                    "question": user_message.content if user_message else "",
                    "legal_basis": snapshot.legal_basis if snapshot else [],
                    "canonical_title": title,
                    "article_no": article_no,
                    "correction_notice": turn.correction_notice,
                }
            )
        return previous_turns

    def _extract_citation_context(self, snapshot: StoredAnswerSnapshot | None) -> tuple[str, str]:
        if snapshot is None or not snapshot.legal_basis:
            return "", ""

        first_citation = snapshot.legal_basis[0]
        match = CITATION_PATTERN.match(first_citation)
        if match is None:
            return "", ""
        return match.group("title") or "", match.group("article") or ""
