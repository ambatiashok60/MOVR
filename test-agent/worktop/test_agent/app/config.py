from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "playwright-agent-service"
    default_model_provider: str | None = None
    default_technology: str = "playwright"
    workspace_root: str = "/tmp"
    enable_targeted_runtime: bool = False
    enable_extended_reporting: bool = False
    validation_timeout_seconds: int = 120
    max_repair_attempts: int = 2
    extension_resolution_agent_retries: int = 1
    placement_resolution_agent_retries: int = 1
    min_placement_confidence: float = 0.5
    min_action_confidence: float = 0.5
    min_ownership_confidence: float = 0.5
    min_flow_merge_confidence: float = 0.5
    budget_max_llm_calls: int = 40
    budget_max_tool_calls: int = 60
    budget_max_repository_reads: int = 200
    budget_max_prompt_chars: int = 1_500_000
    budget_max_generation_seconds: float = 900.0
    budget_enforcement_mode: str = "observe"
    workspace_stale_lock_seconds: float = 3600.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
