from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_prefix: str = "/api"
    workspace_root_allowlist: list[str] = []  # optional: restrict validate-path to these prefixes
    allow_mock_llm: bool = False
    state_backend: str = "sqlite"  # "sqlite" | "mysql" | "memory"
    state_db_path: str = ".ai-workspace-state.sqlite3"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "ai_workspace"
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_state_table: str = "ai_workspace_state"
    budget_max_llm_calls: int = 40
    budget_max_prompt_characters: int = 1_500_000
    budget_max_execution_seconds: float = 900.0
    transaction_root: str = "/tmp"
    workspace_stale_lock_seconds: float = 3600.0

    class Config:
        env_prefix = "AI_WORKSPACE_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
