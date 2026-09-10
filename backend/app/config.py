from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = Field(default="auto", validation_alias="AI_PROVIDER")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    embedding_model: str = Field(default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL")
    chat_model: str = Field(default="gpt-4o-mini", validation_alias="CHAT_MODEL")
    db_path: str = Field(default="./data/knowledge.db", validation_alias="DB_PATH")
    chunk_max_chars: int = Field(default=1000, validation_alias="CHUNK_MAX_CHARS")
    chunk_overlap_chars: int = Field(default=150, validation_alias="CHUNK_OVERLAP_CHARS")
    chunk_min_chars: int = Field(default=50, validation_alias="CHUNK_MIN_CHARS")
    fetch_timeout_seconds: int = Field(default=10, validation_alias="FETCH_TIMEOUT_SECONDS")
    fetch_max_bytes: int = Field(default=5000000, validation_alias="FETCH_MAX_BYTES")
    fetch_user_agent: str = Field(
        default="Mozilla/5.0 (compatible; TuriumBot/1.0; +https://example.com/turium)",
        validation_alias="FETCH_USER_AGENT",
    )
    allow_private_urls: bool = Field(default=False, validation_alias="ALLOW_PRIVATE_URLS")
    default_top_k: int = Field(default=5, validation_alias="DEFAULT_TOP_K")
    max_top_k: int = Field(default=20, validation_alias="MAX_TOP_K")
    offline_embedding_dim: int = Field(default=512, validation_alias="OFFLINE_EMBEDDING_DIM")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def db_path_resolved(self) -> Path:
        return Path(self.db_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def create_settings(**overrides) -> Settings:
    return Settings(**overrides)