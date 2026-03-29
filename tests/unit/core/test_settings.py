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
