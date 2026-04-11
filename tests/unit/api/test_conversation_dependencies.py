from pathlib import Path

from app.api.conversations import get_conversation_service, get_conversation_turn_service
from app.core.settings import Settings
from app.services.context_manager import ContextManager
from app.services.conversation_repository import ConversationRepository
from app.services.conversation_service import ConversationService
from app.services.conversation_summary import ConversationSummaryManager
from app.services.conversation_turn_service import ConversationTurnService
from app.services.knowledge_version import KnowledgeVersionResolver
from app.services.turn_classifier import TurnClassifier


class DummyRetriever:
    def search(self, query, *, top_k):
        del query, top_k
        return []


class DummyChatClient:
    def complete(self, messages):
        del messages
        return {
            "conclusion": "证据不足，无法可靠回答。",
            "citations": [],
            "scope": "",
            "uncertainty": "",
        }


class DummyPresenter:
    def build(self, **kwargs):
        del kwargs
        raise AssertionError("presenter should not be called in dependency construction tests")


def test_get_conversation_service_uses_settings_database_path(tmp_path: Path):
    settings = Settings.model_validate({"conversation_db_path": tmp_path / "conversations.db"})

    service = get_conversation_service(settings)

    assert isinstance(service, ConversationService)
    assert service.repository.db_path == tmp_path / "conversations.db"


def test_get_conversation_turn_service_builds_application_service(tmp_path: Path):
    settings = Settings.model_validate(
        {
            "conversation_db_path": tmp_path / "conversations.db",
            "conversation_summary_trigger_turns": 3,
            "index_dir": tmp_path / "index",
        }
    )
    repository = ConversationRepository(settings.conversation_db_path)
    conversation_service = ConversationService(repository=repository)

    service = get_conversation_turn_service(
        settings=settings,
        repository=repository,
        conversation_service=conversation_service,
        retriever=DummyRetriever(),
        chat_client=DummyChatClient(),
    )

    assert isinstance(service, ConversationTurnService)
    assert service.repository is repository
    assert service.conversation_service is conversation_service
    assert isinstance(service.turn_classifier, TurnClassifier)
    assert isinstance(service.context_manager, ContextManager)
    assert isinstance(service.summary_manager, ConversationSummaryManager)
    assert isinstance(service.knowledge_version_resolver, KnowledgeVersionResolver)
    assert service.summary_trigger_turns == 3
