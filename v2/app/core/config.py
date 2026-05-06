from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CHESS_ARENA_",
        extra="ignore",
    )

    app_name: str = "Chess Arena V2"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")
    database_url: str = Field(
        default="postgresql+asyncpg://chess_arena:chess_arena@localhost:5433/chess_arena"
    )
    redis_url: str = Field(default="redis://localhost:6380/0")


@lru_cache
def get_settings() -> Settings:
    return Settings()

