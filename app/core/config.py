from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    storage_path: str = Field(default="./storage", alias="STORAGE_PATH")
    max_recipients: int = Field(default=1000, alias="MAX_RECIPIENTS", ge=1)
    worker_poll_seconds: float = Field(default=2.0, alias="WORKER_POLL_SECONDS", gt=0)
    job_stale_seconds: int = Field(default=300, alias="JOB_STALE_SECONDS", ge=30)
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
