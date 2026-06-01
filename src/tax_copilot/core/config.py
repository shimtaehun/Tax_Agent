from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET = "dev-secret-change-in-production"  # noqa: S105  # pragma: allowlist secret


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.dev"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SQLAlchemy asyncpg 드라이버용 (postgresql+asyncpg://)
    database_url: str = Field(default="postgresql+asyncpg://tax:tax@localhost:5432/tax_copilot")
    redis_url: str = Field(default="redis://localhost:6379/0")
    secret_key: str = Field(default=_INSECURE_SECRET)
    gemini_api_key: str = Field(default="")
    law_api_key: str = Field(default="")  # 법제처 Open API OC 키
    qdrant_url: str = Field(default="http://localhost:6333")
    storage_backend: str = Field(default="local")
    local_storage_path: str = Field(default="./uploads")
    frontend_url: str = Field(default="http://localhost:3000")
    debug: bool = Field(default=False)

    @field_validator("secret_key")
    @classmethod
    def _reject_insecure_secret(cls, v: str) -> str:
        if v == _INSECURE_SECRET:
            import os

            if os.getenv("DEBUG", "").lower() not in ("1", "true"):
                raise ValueError(  # noqa: E501
                    "SECRET_KEY 환경변수가 설정되지 않았습니다. "
                    "프로덕션에서 기본값은 허용되지 않습니다."
                )
        return v

    @computed_field  # type: ignore[misc]
    @property
    def checkpointer_url(self) -> str:
        """LangGraph PostgreSQL Checkpointer용 psycopg3 형식 URL.

        database_url의 +asyncpg 드라이버 접두사를 제거한다.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


settings = Settings()
