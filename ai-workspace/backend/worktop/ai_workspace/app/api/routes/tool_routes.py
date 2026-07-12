from fastapi import APIRouter, Depends

from worktop.ai_workspace.app.ai_workspace.application.tool_catalog_service import ToolCatalogService
from worktop.ai_workspace.app.ai_workspace.dto.tool_dto import ToolCapabilitiesDto, ToolDefinitionDto, ToolRegistryDto, ToolRuntimeSelectionDto
from worktop.ai_workspace.app.dependencies.ai_workspace_dependencies import get_tool_catalog_service

router = APIRouter(prefix="/ai-workspace/tools", tags=["Tools"])


@router.get("", response_model=ToolRegistryDto)
def get_tools(service: ToolCatalogService = Depends(get_tool_catalog_service)) -> ToolRegistryDto:
    tools = service.list_tools()
    return ToolRegistryDto(
        tools=[
            ToolDefinitionDto(
                id=t.id,
                name=t.name,
                description=t.description,
                capabilities=ToolCapabilitiesDto(
                    reads_files=t.capabilities.reads_files,
                    writes_files=t.capabilities.writes_files,
                    requires_confirmation=t.capabilities.requires_confirmation,
                ),
                parameters_schema=t.parameters_schema,
            )
            for t in tools
        ],
        runtime=ToolRuntimeSelectionDto(enabled_tool_ids=[t.id for t in tools]),
    )


@router.put("/runtime", response_model=ToolRuntimeSelectionDto)
def update_tool_runtime(selection: ToolRuntimeSelectionDto) -> ToolRuntimeSelectionDto:
    return selection
