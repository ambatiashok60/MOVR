from dataclasses import dataclass, field


@dataclass
class ModelLimits:
    context_window_tokens: int
    max_output_tokens: int


@dataclass
class ModelMetadata:
    """Display-only projection of the existing model configuration — AI Workspace never
    stores credentials or provider SDK details itself, it just reflects what
    ModelsConfigurationDAO already knows via model_catalog_service.py."""

    id: str
    display_name: str
    provider_id: str
    limits: ModelLimits
    is_default: bool = False


@dataclass
class ModelRuntimeConfiguration:
    selected_model_id: str
    temperature: float | None = None
    max_output_tokens: int | None = None


@dataclass
class ModelCatalog:
    models: list[ModelMetadata] = field(default_factory=list)
    runtime: ModelRuntimeConfiguration | None = None
