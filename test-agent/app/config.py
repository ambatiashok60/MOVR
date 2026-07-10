from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "playwright-agent-service"
    default_model_provider: str | None = None
    workspace_root: str = "/tmp"
    enable_targeted_runtime: bool = False
    validation_timeout_seconds: int = 120
    max_repair_attempts: int = 2
    min_placement_confidence: float = 0.5
    min_action_confidence: float = 0.5
    min_ownership_confidence: float = 0.5
    min_flow_merge_confidence: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
