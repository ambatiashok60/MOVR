from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API Agent Service"
    max_event_buffer: int = 200
    worker_count: int = 2
    allow_local_llm_fallback: bool = True
    enable_test_execution: bool = True
    max_generation_repair_attempts: int = 2
    execution_timeout_seconds: int = 300
    validation_allowed_executables: tuple[str, ...] = (
        "mvn", "./mvnw", "gradle", "./gradlew", "pytest", "python", "python3", "npm",
    )
    max_execution_repair_attempts: int = 1
    budget_max_llm_calls: int = 40
    budget_max_tool_calls: int = 60
    budget_max_repository_reads: int = 200
    budget_max_prompt_chars: int = 1_500_000
    budget_max_generation_seconds: float = 900.0
    budget_enforcement_mode: str = "review"
    workspace_root: str = "/tmp"
    workspace_stale_lock_seconds: float = 3600.0
    enable_capability_discovery: bool = True
    enable_strategy_reasoning_review: bool = True
    allow_legacy_strategy_fallback: bool = True
    capability_discovery_max_rounds: int = 2
    # ScriptGen-parity route hardening (mirrors worktop.test_agent):
    # in the platform deployment auth middleware populates request.state.tenant_id
    # and this must be True; standalone runs keep the payload-tenant fallback.
    require_authenticated_tenant: bool = False
    # Server-side repository resolution: when the platform datasource DAO is
    # available the configured repo path wins over any client-supplied value.
    default_repo_path: str | None = None
    # Placement of generated tests into existing test files (extend-existing),
    # mirroring worktop.test_agent spec placement.
    enable_test_placement: bool = True
    test_placement_max_turns: int = 3
    # Critic pass over generated tests before they are written and after every
    # repair attempt, mirroring worktop.test_agent critic_review.
    enable_critic_review: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
