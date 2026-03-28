from app.core.settings import Settings


def test_settings_build_default_paths():
    settings = Settings.model_validate({})
    assert settings.data_dir.name == "data"
    assert settings.raw_corpus_dir.name == "法律文本"
