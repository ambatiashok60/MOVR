from fastapi import Depends

from app.common.db import get_db
from app.common.tenancy import get_tenant_id
from app.config.settings import get_settings
from app.llm.application.llm_client_factory import LLMClientFactory
from app.llm.application.llm_application_service import LLMApplicationService
from app.llm.application.llm_gateway import ModelClientFactoryGateway
from app.llm.application.llm_stream_service import LLMStreamService
from app.llm.application.llm_telemetry_service import LLMTelemetryService
from app.llm.infrastructure.default_llm_client_adapter import DefaultLLMClientAdapter
from app.llm.infrastructure.model_client_streaming_adapter import ModelClientStreamingAdapter


def get_llm_telemetry_service() -> LLMTelemetryService:
    # Stateless in V1 (just logs) — fine as a fresh instance per request unlike the
    # stateful stores in container.py.
    return LLMTelemetryService()


def get_llm_application_service(
    db=Depends(get_db), tenant_id: str = Depends(get_tenant_id)
) -> LLMApplicationService:
    # DefaultLLMClient's own constructor takes (db, tenant_id), so the client is constructed
    # per request rather than as a process-lifetime singleton.
    client = LLMClientFactory().create(db=db, tenant_id=tenant_id, allow_mock=get_settings().allow_mock_llm)
    gateway = ModelClientFactoryGateway(client)
    return LLMApplicationService(gateway, get_llm_telemetry_service())


def get_llm_stream_service(db=Depends(get_db), tenant_id: str = Depends(get_tenant_id)) -> LLMStreamService:
    streaming_adapter = ModelClientStreamingAdapter(db=db, tenant_id=tenant_id)
    return LLMStreamService(streaming_adapter)


def get_model_client_factory_adapter(
    db=Depends(get_db), tenant_id: str = Depends(get_tenant_id)
) -> DefaultLLMClientAdapter:
    return DefaultLLMClientAdapter(db=db, tenant_id=tenant_id)
