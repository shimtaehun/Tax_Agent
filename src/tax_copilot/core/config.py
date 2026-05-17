from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = Field(default="postgresql+asyncpg://tax:tax@localhost:5432/tax_copilot")
    redis_url: str = Field(default="redis://localhost:6379/0")
    secret_key: str = Field(default="dev-secret-change-in-production")
    gemini_api_key: str = Field(default="")
    qdrant_url: str = Field(default="http://localhost:6333")
    storage_backend: str = Field(default="local")
    local_storage_path: str = Field(default="./uploads")
    debug: bool = Field(default=False)


settings = Settings()
