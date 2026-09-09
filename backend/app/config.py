from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ForgeGuard Nexus Scientific"
    app_version: str = "0.10.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///runtime-data/forgeguard.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
    knowledge_path: Path = Field(default=Path("./knowledge"))
    model_catalog_path: Path = Field(default=Path("./research/model_catalog.yaml"))
    search_provider: str = "offline"
    searxng_base_url: str | None = None
    search_timeout_seconds: float = 8.0
    search_max_results: int = 8
    reasoning_provider: str = "deterministic"
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    allow_external_search: bool = False
    approval_required_for_high_risk: bool = True
    deployment_profile: str = "portable"
    platform_name: str = "Cross-platform scientific + edge runtime"
    operation_mode: str = "autonomous-experiment-literature-budget-lineage-contradiction-propagation"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="FORGEGUARD_",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
