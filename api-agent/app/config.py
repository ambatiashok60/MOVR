from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "API Agent Service"
    max_event_buffer: int = 200
    worker_count: int = 2


settings = Settings()
