from pathlib import Path

from app.core.settings import Settings


def test_settings_build_default_paths():
    settings = Settings(_env_file=None)
    assert settings.data_dir.name == "data"
    assert settings.raw_corpus_dir.name == "法律文本"
    assert settings.chat_base_url == "https://api.example.com/v1"
    assert settings.chat_timeout_seconds == 30.0


def test_settings_treats_empty_embedding_max_seq_length_as_none(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MAX_SEQ_LENGTH", "")

    settings = Settings()

    assert settings.embedding_max_seq_length is None


def test_settings_build_conversation_defaults():
    settings = Settings.model_validate({})

    assert settings.conversation_db_path == Path("var") / "conversations.db"
    assert settings.conversation_context_window_turns == 4
    assert settings.conversation_summary_trigger_turns == 6


def test_settings_build_incremental_import_paths():
    settings = Settings.model_validate({})

    assert settings.manifests_dir == Path("data") / "manifests"
    assert settings.incremental_staging_dir == Path("data") / ".staging"


def test_settings_build_incremental_paths_from_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom-data"))

    settings = Settings()

    assert settings.data_dir == tmp_path / "custom-data"
    assert settings.manifests_dir == tmp_path / "custom-data" / "manifests"
    assert settings.incremental_staging_dir == tmp_path / "custom-data" / ".staging"
