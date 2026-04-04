from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_api_key: str = Field(default="change-me", alias="APP_API_KEY")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="olist", alias="POSTGRES_DB")
    postgres_user: str = Field(default="olist", alias="POSTGRES_USER")
    postgres_password: str = Field(default="olist", alias="POSTGRES_PASSWORD")
    db_statement_timeout_ms: int = Field(default=120000, alias="DB_STATEMENT_TIMEOUT_MS")

    data_dir: str = Field(default="./data", alias="DATA_DIR")

    llm_provider: str = Field(default="none", alias="LLM_PROVIDER")
    llm_enable_thinking: bool = Field(default=False, alias="LLM_ENABLE_THINKING")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    model_api_base: str = Field(default="", alias="MODEL_API_BASE")
    temperature: float = Field(default=0.0, alias="TEMPERATURE")
    base_url: str = Field(default="", alias="BASE_URL")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

    @property
    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
