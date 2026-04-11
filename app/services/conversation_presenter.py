from collections.abc import Mapping
from typing import Any

from app.schemas.conversation import AssistantMessagePayload


class ConversationPresenter:
    CORRECTION_NOTICE = "本轮已根据最新检索证据修正前文。"

    def build(
        self,
        *,
        answer: Mapping[str, Any] | Any,
        previous_snapshot: Mapping[str, Any] | Any | None,
        is_followup: bool,
        message_id: str = "",
        created_at: str = "",
    ) -> AssistantMessagePayload:
        legal_basis = list(self._get(answer, "citations", []))
        current_clause_texts = [
            {"path": item["path"], "text": item["text"]}
            for item in list(self._get(answer, "evidence", []))
        ]

        if is_followup and previous_snapshot is not None:
            previous_legal_basis = list(self._get(previous_snapshot, "legal_basis", []))
            previous_clause_texts = list(self._get(previous_snapshot, "clause_texts", []))
            if previous_legal_basis == legal_basis:
                clause_texts = previous_clause_texts or current_clause_texts
                correction_notice = ""
            else:
                clause_texts = current_clause_texts
                correction_notice = self.CORRECTION_NOTICE
        else:
            clause_texts = current_clause_texts
            correction_notice = ""

        return AssistantMessagePayload(
            message_id=message_id,
            answer=str(self._get(answer, "conclusion", "")),
            legal_basis=legal_basis,
            clause_texts=clause_texts,
            correction_notice=correction_notice,
            created_at=created_at,
        )

    def _get(self, payload: Mapping[str, Any] | Any, key: str, default: Any) -> Any:
        if isinstance(payload, Mapping):
            return payload.get(key, default)
        return getattr(payload, key, default)
