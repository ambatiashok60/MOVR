from dataclasses import dataclass, field

from .model_metadata import ModelCatalog
from .tool_definition import ToolDefinition


@dataclass
class FeatureFlags:
    flags: dict = field(default_factory=dict)


@dataclass
class UserPermissions:
    can_run_agent: bool
    can_apply_changes: bool
    can_edit_settings: bool


@dataclass
class BootstrapState:
    """Single payload returned by GET /api/ai-workspace/bootstrap — see
    bootstrap_service.py. Mirrors the frontend's BootstrapPayload model 1:1."""

    models: ModelCatalog
    tools: list[ToolDefinition]
    feature_flags: FeatureFlags
    permissions: UserPermissions
