from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="RAG Books MVP", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    raw_dir: Path = Field(default=Path("./data/raw"), alias="RAW_DIR")
    parsed_dir: Path = Field(default=Path("./data/parsed"), alias="PARSED_DIR")
    index_dir: Path = Field(default=Path("./data/indexes"), alias="INDEX_DIR")
    lightrag_workdir: Path = Field(default=Path("./data/lightrag"), alias="LIGHTRAG_WORKDIR")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")
    router_model: str = Field(default="gpt-5-mini", alias="ROUTER_MODEL")
    llm_healthcheck_url: str | None = Field(default=None, alias="LLM_HEALTHCHECK_URL")
    llm_restart_command: str | None = Field(default=None, alias="LLM_RESTART_COMMAND")
    llm_restart_timeout_seconds: int = Field(default=180, alias="LLM_RESTART_TIMEOUT_SECONDS")
    llm_restart_poll_interval_seconds: float = Field(default=3.0, alias="LLM_RESTART_POLL_INTERVAL_SECONDS")
    llm_call_retry_attempts: int = Field(default=2, alias="LLM_CALL_RETRY_ATTEMPTS")
    embedding_base_url: str | None = Field(default=None, alias="EMBEDDING_BASE_URL")
    embedding_api_key: str | None = Field(default=None, alias="EMBEDDING_API_KEY")
    embedding_model: str | None = Field(default=None, alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for path in (
        settings.data_dir,
        settings.raw_dir,
        settings.parsed_dir,
        settings.index_dir,
        settings.lightrag_workdir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return settings
