from collections.abc import Iterator, Mapping
from dataclasses import replace
import re
from typing import Any

from app.schemas.conversation import ConversationStreamEvent, SendConversationMessageResponse
from app.services.answer_service import build_answer, is_model_failure_uncertainty
from app.services.chat_client import ChatCompletionError
from app.services.conversation_repository import ConversationDetail, ConversationRepository, StoredAnswerSnapshot
from app.services.conversation_service import ConversationService
from app.services.query_normalizer import NormalizedQuery, normalize_query


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

    def handle_user_message_stream(self, conversation_id: str, message: str) -> Iterator[ConversationStreamEvent]:
        detail = self.repository.get_conversation_detail(conversation_id)
        previous_turns = self._build_previous_turns(detail)
        previous_snapshot = detail.snapshots[-1] if detail.snapshots else None

        user_message = self.repository.append_message(conversation_id, role="user", content=message)
        if not detail.messages:
            self.conversation_service.note_first_user_message(conversation_id, message)

        yield ConversationStreamEvent(event="received", data={"persisted": True})

        yield ConversationStreamEvent(event="retrieving")
        classification = self.turn_classifier.classify(message, previous_turns=previous_turns)
        history_summary = self._build_history_summary(previous_turns)
        context = self.context_manager.build(previous_turns, history_summary=history_summary)
        normalized = self._apply_context_to_query(
            normalize_query(message, context_hints=classification.context_hints),
            context,
        )
        evidence = self.retriever.search(normalized, top_k=self.retrieval_top_k)
        
        yield ConversationStreamEvent(event="generating")
        answer = build_answer(evidence, client=self.chat_client, question=message)
        if is_model_failure_uncertainty(answer.get("uncertainty")):
            raise ChatCompletionError(str(answer["uncertainty"]))

        yield ConversationStreamEvent(event="organizing_evidence")
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
        current_history_summary = self._build_history_summary(
            [
                *previous_turns,
                self._build_turn_context(
                    question=user_message.content,
                    legal_basis=assistant_payload.legal_basis,
                    correction_notice=assistant_payload.correction_notice,
                ),
            ]
        )
        self.repository.save_history_summary(conversation_id, current_history_summary)

        payload = self.presenter.build(
            answer=answer,
            previous_snapshot=previous_snapshot,
            is_followup=classification.is_followup,
            message_id=assistant_message.id,
            created_at=assistant_message.created_at,
        )

        if snapshot.turn_id != turn.id:
            raise RuntimeError("snapshot was not persisted for the created turn")
            
        yield ConversationStreamEvent(event="completed", assistant=payload)

    def handle_user_message(self, conversation_id: str, message: str) -> SendConversationMessageResponse:
        assistant = None
        for event in self.handle_user_message_stream(conversation_id, message):
            if event.event == "completed" and event.assistant:
                assistant = event.assistant
        if not assistant:
            raise RuntimeError("stream did not complete")
        return SendConversationMessageResponse(assistant=assistant)

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

    def _build_turn_context(
        self,
        *,
        question: str,
        legal_basis: list[str],
        correction_notice: str,
    ) -> dict[str, Any]:
        title, article_no = self._extract_citation_context_from_basis(legal_basis)
        return {
            "question": question,
            "legal_basis": legal_basis,
            "canonical_title": title,
            "article_no": article_no,
            "correction_notice": correction_notice,
        }

    def _extract_citation_context_from_basis(self, legal_basis: list[str]) -> tuple[str, str]:
        if not legal_basis:
            return "", ""
        match = CITATION_PATTERN.match(legal_basis[0])
        if match is None:
            return "", ""
        return match.group("title") or "", match.group("article") or ""

    def _apply_context_to_query(self, normalized: NormalizedQuery, context: Any) -> NormalizedQuery:
        recent_fragments: list[str] = []
        for turn in context.recent_turns:
            question = str(turn.get("question", "") or "").strip()
            if question:
                recent_fragments.append(question)
            recent_fragments.extend(
                citation
                for citation in (str(item).strip() for item in turn.get("legal_basis", []))
                if citation
            )

        if not recent_fragments and not context.history_summary:
            return normalized

        rewritten_terms = self._unique_terms([normalized.rewritten_query or normalized.cleaned, *recent_fragments])
        vector_terms = self._unique_terms(
            [
                normalized.vector_query or normalized.cleaned,
                *recent_fragments,
                context.history_summary,
            ]
        )
        keyword_terms = self._unique_terms([*normalized.keyword_terms, *recent_fragments, context.history_summary])
        return replace(
            normalized,
            rewritten_query=" ".join(rewritten_terms),
            vector_query=" ".join(vector_terms),
            keyword_terms=keyword_terms,
        )

    def _unique_terms(self, values: list[str]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            terms.append(text)
        return terms
