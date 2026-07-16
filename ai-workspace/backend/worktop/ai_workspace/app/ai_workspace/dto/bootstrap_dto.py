from .base import CamelModel
from .model_dto import ModelCatalogDto
from .tool_dto import ToolRegistryDto
from .workspace_dto import WorkspaceInfoDto


class FeatureFlagsDto(CamelModel):
    flags: dict = {}


class UserPermissionsDto(CamelModel):
    can_run_agent: bool
    can_apply_changes: bool
    can_edit_settings: bool


class UserPreferencesDto(CamelModel):
    default_mode: str = "agent"
    theme: str | None = None


class PlannerConfigDto(CamelModel):
    max_plan_steps: int = 8


class ExecutionConfigDto(CamelModel):
    sse_endpoint: str = "/api/ai-workspace/agent/executions/{executionId}/events"
    poll_interval_ms: int | None = 5000


class TelemetryConfigDto(CamelModel):
    enabled: bool = False
    endpoint: str | None = None


class BootstrapDto(CamelModel):
    workspace: WorkspaceInfoDto | None = None
    models: ModelCatalogDto
    tools: ToolRegistryDto
    feature_flags: dict = {}
    permissions: UserPermissionsDto
    preferences: UserPreferencesDto
    planner: PlannerConfigDto = PlannerConfigDto()
    execution: ExecutionConfigDto = ExecutionConfigDto()
    telemetry: TelemetryConfigDto = TelemetryConfigDto()
