from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    raw_corpus_dir: Path = Path("法律文本")
    index_dir: Path = Path("data") / "index"
    conversation_db_path: Path = Path("var") / "conversations.db"
    conversation_context_window_turns: int = 4
    conversation_summary_trigger_turns: int = 6
    chat_api_key: str = "replace-me"
    chat_base_url: str = "https://api.example.com/v1"
    chat_model: str = "replace-me"
    chat_timeout_seconds: float = 30.0
    chat_temperature: float = 0.0
    embedding_model_name: str | None = None
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    embedding_max_seq_length: int | None = None

    @field_validator("embedding_max_seq_length", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def manifests_dir(self) -> Path:
        return self.data_dir / "manifests"

    @property
    def incremental_staging_dir(self) -> Path:
        return self.data_dir / ".staging"


@lru_cache
def get_settings() -> Settings:
    return Settings()
