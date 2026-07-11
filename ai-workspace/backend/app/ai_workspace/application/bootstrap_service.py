from app.ai_workspace.application.model_catalog_service import ModelCatalogService
from app.ai_workspace.application.tool_catalog_service import ToolCatalogService
from app.ai_workspace.domain.bootstrap_state import BootstrapState, FeatureFlags, UserPermissions


class BootstrapService:
    """Single startup payload for the frontend — one call instead of the frontend making N
    separate requests before it can render anything. See ai_workspace_routes.py's
    GET /api/ai-workspace/bootstrap."""

    def __init__(self, model_catalog_service: ModelCatalogService, tool_catalog_service: ToolCatalogService):
        self._model_catalog_service = model_catalog_service
        self._tool_catalog_service = tool_catalog_service

    def build(self) -> BootstrapState:
        return BootstrapState(
            models=self._model_catalog_service.get_catalog(),
            tools=self._tool_catalog_service.list_tools(),
            feature_flags=FeatureFlags(flags={}),
            permissions=UserPermissions(can_run_agent=True, can_apply_changes=True, can_edit_settings=True),
        )
