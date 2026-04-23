from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    auto_title: bool
    updated_at: str
    last_message_at: str | None = None


class ClauseTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    text: str


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    content: str
    created_at: str
    legal_basis: list[str] = Field(default_factory=list)
    clause_texts: list[ClauseTextPayload] = Field(default_factory=list)
    correction_notice: str = ""


class AssistantMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = ""
    answer: str = Field(min_length=1)
    legal_basis: list[str] = Field(default_factory=list)
    clause_texts: list[ClauseTextPayload] = Field(default_factory=list)
    correction_notice: str = ""
    created_at: str = ""


class ConversationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationListItem
    messages: list[ConversationMessage] = Field(default_factory=list)
    history_summary: str = ""


class UserMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)


class RenameConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)


class SendConversationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant: AssistantMessagePayload


class ConversationStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["received", "retrieving", "generating", "organizing_evidence", "completed", "error"]
    message: str | None = None
    persisted: bool | None = None
    retryable: bool | None = None
    assistant: AssistantMessagePayload | None = None
    code: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_stream_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "type" not in payload and "event" in payload:
            payload["type"] = payload.pop("event")

        legacy_data = payload.pop("data", None)
        if isinstance(legacy_data, dict):
            if "persisted" not in payload and "persisted" in legacy_data:
                payload["persisted"] = bool(legacy_data["persisted"])
            if "message" not in payload and legacy_data.get("message") is not None:
                payload["message"] = str(legacy_data["message"])

        return payload

    @property
    def event(self) -> str:
        return self.type

    @property
    def data(self) -> dict[str, Any] | None:
        if self.persisted is None:
            return None
        return {"persisted": self.persisted}
