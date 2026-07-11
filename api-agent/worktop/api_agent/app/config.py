from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "API Agent Service"
    max_event_buffer: int = 200
    worker_count: int = 2
    enable_test_execution: bool = False
    max_generation_repair_attempts: int = 2
    execution_timeout_seconds: int = 300
    max_execution_repair_attempts: int = 1
    budget_max_llm_calls: int = 40
    budget_max_tool_calls: int = 60
    budget_max_repository_reads: int = 200
    budget_max_prompt_chars: int = 1_500_000
    budget_max_generation_seconds: float = 900.0


settings = Settings()
