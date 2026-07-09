from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.api_repo_context_service import ApiRepoContextService
from app.tools.path_safety import resolve_workspace_path


class ApiRepoProfileService:
    profile_name = "api_repo_profile.json"

    def __init__(self) -> None:
        self.context = ApiRepoContextService()

    def profile_path(self, repo_path: str) -> Path:
        return resolve_workspace_path(repo_path) / self.profile_name

    def check(self, repo_path: str) -> dict[str, Any]:
        path = self.profile_path(repo_path)
        return {
            "exists": path.exists(),
            "resolved_path": str(path),
            "message": (
                "api_repo_profile.json found."
                if path.exists()
                else f"api_repo_profile.json not found at {path}."
            ),
        }

    def generate(self, repo_path: str, overwrite: bool = False) -> dict[str, Any]:
        path = self.profile_path(repo_path)
        if path.exists() and not overwrite:
            return {
                "generated": False,
                "profile_path": str(path),
                "profile": json.loads(path.read_text(encoding="utf-8")),
                "message": "api_repo_profile.json already exists.",
            }

        profile = self.context.build(repo_path)
        profile_data = profile.model_dump(mode="json")
        path.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")
        return {
            "generated": True,
            "profile_path": str(path),
            "profile": profile_data,
            "message": "api_repo_profile.json generated.",
        }
