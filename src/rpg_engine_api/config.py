from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration. No network/database work occurs while constructing settings."""

    model_config = SettingsConfigDict(
        env_prefix="RPG_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    persistence_backend: Literal["memory", "postgres"] = "memory"
    database_url: str | None = None
    default_principal_id: str = "local-player"

    @property
    def postgres_configured(self) -> bool:
        return self.persistence_backend == "postgres" and bool(self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
