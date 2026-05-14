from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CHESS_ARENA_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Chess Arena V2"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("CHESS_ARENA_ENVIRONMENT", "CHESS_ARENA_ENV"),
    )
    database_url: str = Field(
        default="postgresql+asyncpg://chess_arena:chess_arena@localhost:5433/chess_arena"
    )
    redis_url: str = Field(default="redis://localhost:6380/0")
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8001"]
    )
    secret_key: str = Field(default="dev-only-secret")
    rate_limit_capacity: int = Field(default=60, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    strict_health_checks: bool = False

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one CORS origin must be configured")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment == "production":
            unsafe_database_fragments = ("localhost", "127.0.0.1", "chess_arena:chess_arena")
            if any(fragment in self.database_url for fragment in unsafe_database_fragments):
                raise ValueError("production database_url must not use local/default credentials")
            if "localhost" in self.redis_url or "127.0.0.1" in self.redis_url:
                raise ValueError("production redis_url must not use localhost")
            if "*" in self.cors_allowed_origins:
                raise ValueError("production CORS origins must be explicit")
            if self.secret_key == "dev-only-secret" or len(self.secret_key) < 32:
                raise ValueError("production secret_key must be set to a strong value")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
