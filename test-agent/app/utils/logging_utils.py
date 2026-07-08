from __future__ import annotations

from typing import Any


LOG_METADATA_KEYS = (
    "job_id",
    "tenant_id",
    "repo_path",
    "branch",
    "stage",
    "agent_name",
)


def build_log_context(**metadata: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key in LOG_METADATA_KEYS and value is not None
    }
