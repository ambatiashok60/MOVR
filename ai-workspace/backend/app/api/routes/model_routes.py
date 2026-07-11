from fastapi import APIRouter, Depends

from app.ai_workspace.application.model_catalog_service import ModelCatalogService
from app.ai_workspace.dto.model_dto import (
    ModelCatalogDto,
    ModelLimitsDto,
    ModelMetadataDto,
    ModelRuntimeConfigurationDto,
    UpdateRuntimeConfigRequest,
)
from app.dependencies.ai_workspace_dependencies import get_model_catalog_service

router = APIRouter(prefix="/ai-workspace/models", tags=["Models"])


@router.get("", response_model=ModelCatalogDto)
def get_models(service: ModelCatalogService = Depends(get_model_catalog_service)) -> ModelCatalogDto:
    catalog = service.get_catalog()
    return _to_dto(catalog)


@router.put("/runtime", response_model=ModelRuntimeConfigurationDto)
def update_runtime(
    request: UpdateRuntimeConfigRequest, service: ModelCatalogService = Depends(get_model_catalog_service)
) -> ModelRuntimeConfigurationDto:
    runtime = service.update_runtime_config(request.selected_model_id)
    return ModelRuntimeConfigurationDto(selected_model_id=runtime.selected_model_id)


def _to_dto(catalog) -> ModelCatalogDto:
    return ModelCatalogDto(
        models=[
            ModelMetadataDto(
                id=m.id,
                display_name=m.display_name,
                provider_id=m.provider_id,
                limits=ModelLimitsDto(
                    context_window_tokens=m.limits.context_window_tokens, max_output_tokens=m.limits.max_output_tokens
                ),
                is_default=m.is_default,
            )
            for m in catalog.models
        ],
        runtime=ModelRuntimeConfigurationDto(selected_model_id=catalog.runtime.selected_model_id)
        if catalog.runtime
        else None,
    )
