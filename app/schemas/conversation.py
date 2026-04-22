from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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

    event: str
    data: dict[str, Any] | None = None
    assistant: AssistantMessagePayload | None = None
    code: str | None = None
