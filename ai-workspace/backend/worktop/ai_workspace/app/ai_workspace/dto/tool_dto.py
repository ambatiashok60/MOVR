from pydantic import Field

from .base import CamelModel


class ToolCapabilitiesDto(CamelModel):
    reads_files: bool
    writes_files: bool
    requires_confirmation: bool


class ToolDefinitionDto(CamelModel):
    id: str
    name: str
    description: str
    capabilities: ToolCapabilitiesDto
    parameters_schema: dict = Field(default_factory=dict, alias="schema")


class ToolRuntimeSelectionDto(CamelModel):
    enabled_tool_ids: list[str]


class ToolRegistryDto(CamelModel):
    tools: list[ToolDefinitionDto]
    runtime: ToolRuntimeSelectionDto
