from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    raw_corpus_dir: Path = Path("法律文本")
    index_dir: Path = Path("data") / "index"
    embedding_model_name: str | None = None
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    embedding_max_seq_length: int | None = None
