from fastapi import Depends

from app.ai_workspace.application.agent.agent_service import AgentService
from app.ai_workspace.application.bootstrap_service import BootstrapService
from app.ai_workspace.application.chat.chat_service import ChatService
from app.ai_workspace.application.context.context_builder_service import ContextBuilderService
from app.ai_workspace.application.execution.execution_event_service import ExecutionEventService
from app.ai_workspace.application.execution.execution_orchestrator import ExecutionOrchestrator
from app.ai_workspace.application.model_catalog_service import ModelCatalogService
from app.ai_workspace.application.prompts.prompt_builder_service import PromptBuilderService
from app.ai_workspace.application.prompts.prompt_renderer import PromptRenderer
from app.ai_workspace.application.review.diff_service import DiffService
from app.ai_workspace.application.review.review_service import ReviewService
from app.ai_workspace.application.sessions.session_service import SessionService
from app.ai_workspace.application.tools.apply_patch_tool import ApplyPatchTool
from app.ai_workspace.application.tools.tool_execution_service import ToolExecutionService
from app.ai_workspace.application.agent.patch_validation_service import PatchValidationService
from app.ai_workspace.application.review.engineering_review_service import EngineeringReviewService
from app.ai_workspace.application.tool_catalog_service import ToolCatalogService
from app.ai_workspace.application.workspace_path_service import WorkspacePathService
from app.ai_workspace.application.workspace_runtime_service import WorkspaceRuntimeService
from app.ai_workspace.domain.execution_context import ExecutionContext
from app.ai_workspace.domain.workspace_mode import WorkspaceMode
from app.common.db import get_db
from app.common.tenancy import get_tenant_id
from app.dependencies.container import container
from app.dependencies.llm_dependencies import get_llm_application_service
from app.dependencies.repository_dependencies import get_file_read_service, get_file_write_service


def get_session_service() -> SessionService:
    return SessionService(container.session_store)


def get_workspace_runtime_service() -> WorkspaceRuntimeService:
    return WorkspaceRuntimeService(container.runtime_store)


def get_workspace_path_service() -> WorkspacePathService:
    return WorkspacePathService(container.local_workspace_provider, container.repository_scan_service)


def get_context_builder_service() -> ContextBuilderService:
    return ContextBuilderService(get_file_read_service(), get_session_service())


def get_prompt_builder_service() -> PromptBuilderService:
    return PromptBuilderService(container.repository_memory_service)


def get_prompt_renderer() -> PromptRenderer:
    return PromptRenderer()


def get_diff_service() -> DiffService:
    return DiffService()


def get_execution_event_service() -> ExecutionEventService:
    return ExecutionEventService(container.sse_publisher)


def get_review_service() -> ReviewService:
    apply_patch_tool = ApplyPatchTool(container.review_store, get_file_write_service(), container.workspace_transaction_service)
    return ReviewService(container.review_store, apply_patch_tool)


def get_model_catalog_service(db=Depends(get_db), tenant_id: str = Depends(get_tenant_id)) -> ModelCatalogService:
    return ModelCatalogService(db=db, tenant_id=tenant_id)


def get_tool_catalog_service() -> ToolCatalogService:
    return ToolCatalogService(container.tool_registry)


def get_bootstrap_service(
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service),
) -> BootstrapService:
    return BootstrapService(model_catalog_service, get_tool_catalog_service())


def get_chat_service(llm_service=Depends(get_llm_application_service)) -> ChatService:
    return ChatService(
        context_builder=get_context_builder_service(),
        prompt_builder=get_prompt_builder_service(),
        prompt_renderer=get_prompt_renderer(),
        llm_service=llm_service,
        session_service=get_session_service(),
    )


def get_agent_service(llm_service=Depends(get_llm_application_service)) -> AgentService:
    return AgentService(
        context_builder=get_context_builder_service(),
        prompt_builder=get_prompt_builder_service(),
        prompt_renderer=get_prompt_renderer(),
        llm_service=llm_service,
        session_service=get_session_service(),
        file_read_service=get_file_read_service(),
        diff_service=get_diff_service(),
        review_service=get_review_service(),
        plan_store=container.plan_store,
        tool_execution_service=ToolExecutionService(container.tool_registry),
        event_service=get_execution_event_service(),
        patch_validator=PatchValidationService(),
        engineering_review_service=EngineeringReviewService(),
        isolated_workspace_service=container.isolated_workspace_service,
        repository_memory_service=container.repository_memory_service,
    )


def get_execution_orchestrator(
    chat_service: ChatService = Depends(get_chat_service),
    agent_service: AgentService = Depends(get_agent_service),
) -> ExecutionOrchestrator:
    strategies = {WorkspaceMode.CHAT: chat_service, WorkspaceMode.AGENT: agent_service}
    return ExecutionOrchestrator(
        strategies, get_workspace_runtime_service(), get_execution_event_service(), container.execution_store
    )


def get_execution_by_id(execution_id: str) -> ExecutionContext | None:
    return container.execution_store.get(execution_id)


def get_plan_by_execution_id(execution_id: str):
    return container.plan_store.get(execution_id)
