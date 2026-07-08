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

    class Config:
        env_prefix = "AI_WORKSPACE_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
