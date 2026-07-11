from dataclasses import dataclass, field


@dataclass
class ToolCapabilities:
    reads_files: bool
    writes_files: bool
    requires_confirmation: bool


@dataclass
class ToolDefinition:
    id: str
    name: str
    description: str
    capabilities: ToolCapabilities
    parameters_schema: dict = field(default_factory=dict)
