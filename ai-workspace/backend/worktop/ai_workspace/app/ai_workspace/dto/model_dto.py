from .base import CamelModel


class ModelCapabilitiesDto(CamelModel):
    supports_tools: bool = False
    supports_streaming: bool = False
    supports_vision: bool = False


class ModelLimitsDto(CamelModel):
    context_window_tokens: int
    max_output_tokens: int


class ModelMetadataDto(CamelModel):
    id: str
    display_name: str
    provider_id: str
    capabilities: ModelCapabilitiesDto = ModelCapabilitiesDto()
    limits: ModelLimitsDto
    is_default: bool = False


class ModelRuntimeConfigurationDto(CamelModel):
    selected_model_id: str
    temperature: float | None = None
    max_output_tokens: int | None = None


class ModelCatalogDto(CamelModel):
    models: list[ModelMetadataDto]
    runtime: ModelRuntimeConfigurationDto | None = None


class UpdateRuntimeConfigRequest(CamelModel):
    selected_model_id: str
