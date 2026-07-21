"""Central configuration. All tunables live here and are environment-overridable.

Nothing in the agent logic should hardcode a model id, timeout, or threshold; it
reads from the singleton `settings` object instead.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPO_AGENT_", extra="ignore")

    # --- Persistence -------------------------------------------------------
    database_path: str = "./repo_agent.db"

    # --- Agent loop / conversation ----------------------------------------
    max_agent_iterations: int = 20
    max_full_turns: int = 20
    compaction_trigger_turns: int = 16
    recent_turns_to_keep: int = 6
    max_summary_tokens: int = 3_000

    # --- Context batching --------------------------------------------------
    max_files_per_context_batch: int = 8
    max_context_tokens_per_batch: int = 12_000
    max_response_tokens_per_batch: int = 2_500
    max_search_results_per_batch: int = 20
    max_directory_depth: int = 6

    # --- Tool / command limits --------------------------------------------
    max_tool_output_chars: int = 40_000
    max_command_output_chars: int = 50_000
    default_command_timeout_seconds: int = 120
    llm_request_timeout_seconds: int = 180

    # --- Stale-run watchdog (backend) -------------------------------------
    heartbeat_interval_seconds: int = 15
    run_stale_warning_seconds: int = 240
    run_stale_failure_seconds: int = 600

    # --- LLM / AWS ---------------------------------------------------------
    # "fake" keeps everything local & deterministic. "bedrock" uses boto3.
    llm_provider: str = "fake"
    aws_profile: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    # --- HTTP --------------------------------------------------------------
    cors_allow_origins: str = "http://localhost:4200,http://127.0.0.1:4200"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
