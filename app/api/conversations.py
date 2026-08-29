from collections.abc import Mapping
import inspect
from typing import Annotated, Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.api.chat import get_chat_client, get_retriever
from app.core.settings import Settings, get_settings
from app.schemas.conversation import (
    ConversationDetail,
    ConversationListItem,
    ConversationMessage,
    ConversationStreamEvent,
    RenameConversationInput,
    SendConversationMessageResponse,
    UserMessageInput,
)
from app.services.context_manager import ContextManager
from app.services.conversation_presenter import ConversationPresenter
from app.services.conversation_repository import ConversationNotFoundError, ConversationRepository
from app.services.conversation_service import ConversationService
from app.services.conversation_summary import ConversationSummaryManager
from app.services.conversation_turn_service import ConversationTurnService
from app.services.chat_client import ChatCompletionError
from app.services.knowledge_version import KnowledgeVersionResolver
from app.services.turn_classifier import TurnClassifier


MISSING_CONVERSATION_DETAIL = "会话不存在或已删除"

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def get_conversation_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationRepository:
    return ConversationRepository(settings.conversation_db_path)


def get_conversation_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationService:
    return ConversationService(repository=ConversationRepository(settings.conversation_db_path))


def get_conversation_turn_service(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    retriever: Annotated[Any, Depends(get_retriever)],
    chat_client: Annotated[Any, Depends(get_chat_client)],
) -> ConversationTurnService:
    return ConversationTurnService(
        repository=repository,
        conversation_service=conversation_service,
        turn_classifier=TurnClassifier(),
        context_manager=ContextManager(window_turns=settings.conversation_context_window_turns),
        summary_manager=ConversationSummaryManager(),
        knowledge_version_resolver=KnowledgeVersionResolver(index_dir=settings.index_dir),
        retriever=retriever,
        chat_client=chat_client,
        presenter=ConversationPresenter(),
        summary_trigger_turns=settings.conversation_summary_trigger_turns,
    )


ConversationTurnServiceFactory = Callable[[], Awaitable[ConversationTurnService]]


def get_conversation_turn_service_factory(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationTurnServiceFactory:
    async def _build() -> ConversationTurnService:
        retriever_dependency = request.app.dependency_overrides.get(get_retriever, get_retriever)
        chat_client_dependency = request.app.dependency_overrides.get(get_chat_client, get_chat_client)
        retriever = await _call_dependency(retriever_dependency, settings=settings)
        chat_client = await _call_dependency(chat_client_dependency, settings=settings)
        return ConversationTurnService(
            repository=repository,
            conversation_service=conversation_service,
            turn_classifier=TurnClassifier(),
            context_manager=ContextManager(window_turns=settings.conversation_context_window_turns),
            summary_manager=ConversationSummaryManager(),
            knowledge_version_resolver=KnowledgeVersionResolver(index_dir=settings.index_dir),
            retriever=retriever,
            chat_client=chat_client,
            presenter=ConversationPresenter(),
            summary_trigger_turns=settings.conversation_summary_trigger_turns,
        )

    return _build


@router.post("", response_model=ConversationListItem, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationInput,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationListItem:
    del payload
    return _serialize_conversation(service.create_conversation())


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> list[ConversationListItem]:
    return [_serialize_conversation(item) for item in service.list_conversations()]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(
    conversation_id: str,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationDetail:
    try:
        detail = service.get_conversation_detail(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=MISSING_CONVERSATION_DETAIL) from exc
    return _serialize_detail(detail)


@router.patch("/{conversation_id}", response_model=ConversationListItem)
async def rename_conversation(
    conversation_id: str,
    payload: RenameConversationInput,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationListItem:
    try:
        conversation = service.rename_conversation(conversation_id, payload.title)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=MISSING_CONVERSATION_DETAIL) from exc
    return _serialize_conversation(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> Response:
    try:
        service.delete_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=MISSING_CONVERSATION_DETAIL) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/messages", response_model=SendConversationMessageResponse)
async def send_message(
    conversation_id: str,
    payload: UserMessageInput,
    service: Annotated[ConversationTurnService, Depends(get_conversation_turn_service)],
) -> SendConversationMessageResponse:
    try:
        result = service.handle_user_message(conversation_id, payload.message)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=MISSING_CONVERSATION_DETAIL) from exc
    except ChatCompletionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SendConversationMessageResponse.model_validate(result, from_attributes=True)


@router.post("/{conversation_id}/messages/stream", response_class=StreamingResponse)
async def send_message_stream(
    conversation_id: str,
    payload: UserMessageInput,
    service_factory: Annotated[ConversationTurnServiceFactory, Depends(get_conversation_turn_service_factory)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> StreamingResponse:
    try:
        conversation_service.get_conversation_detail(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=MISSING_CONVERSATION_DETAIL) from exc

    service = await service_factory()

    def event_generator():
        received_sent = False
        try:
            for event in service.handle_user_message_stream(conversation_id, payload.message):
                if event.type == "received":
                    received_sent = True
                yield event.model_dump_json(exclude_none=True) + "\n"
        except ChatCompletionError as exc:
            error_event = ConversationStreamEvent(
                type="error",
                code="model_error",
                message=str(exc),
                retryable=True,
            )
            yield error_event.model_dump_json(exclude_none=True) + "\n"
        except ConversationNotFoundError:
            if received_sent:
                # 「已知限制」：received 发出后的会话删除第一版不做精确归因，按 internal_error 处理。
                error_event = ConversationStreamEvent(
                    type="error",
                    code="internal_error",
                    message="服务内部异常，请稍后重试。",
                    retryable=True,
                )
            else:
                error_event = ConversationStreamEvent(
                    type="error",
                    code="conversation_not_found",
                    message=MISSING_CONVERSATION_DETAIL,
                    retryable=False,
                )
            yield error_event.model_dump_json(exclude_none=True) + "\n"
        except Exception:
            error_event = ConversationStreamEvent(
                type="error",
                code="internal_error",
                message="服务内部异常，请稍后重试。",
                retryable=True,
            )
            yield error_event.model_dump_json(exclude_none=True) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson; charset=utf-8"
    )

def _serialize_conversation(item: Any) -> ConversationListItem:
    return ConversationListItem.model_validate(item, from_attributes=True)


def _serialize_detail(detail: Any) -> ConversationDetail:
    conversation = _serialize_conversation(_get(detail, "conversation"))
    message_items = list(_get(detail, "messages", []))
    turn_items = list(_get(detail, "turns", []))
    snapshot_items = list(_get(detail, "snapshots", []))
    history_summary = str(_get(detail, "history_summary", "") or "")

    snapshots_by_turn_id = {_get(snapshot, "turn_id"): snapshot for snapshot in snapshot_items}
    assistant_metadata: dict[str, dict[str, Any]] = {}
    for turn in turn_items:
        snapshot = snapshots_by_turn_id.get(_get(turn, "id"))
        if snapshot is None:
            continue
        assistant_metadata[str(_get(turn, "assistant_message_id"))] = {
            "legal_basis": list(_get(snapshot, "legal_basis", [])),
            "clause_texts": list(_get(snapshot, "clause_texts", [])),
            "correction_notice": str(_get(turn, "correction_notice", "") or ""),
        }

    messages: list[ConversationMessage] = []
    for message in message_items:
        payload = ConversationMessage.model_validate(message, from_attributes=True)
        if payload.id in assistant_metadata:
            payload = ConversationMessage.model_validate(
                payload.model_dump(mode="json") | assistant_metadata[payload.id]
            )
        messages.append(payload)

    return ConversationDetail(
        conversation=conversation,
        messages=messages,
        history_summary=history_summary,
    )


def _get(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


async def _call_dependency(dependency: Callable[..., Any], /, **kwargs: Any) -> Any:
    signature = inspect.signature(dependency)
    call_kwargs = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
    }
    result = dependency(**call_kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
