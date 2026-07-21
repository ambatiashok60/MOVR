from fastapi import APIRouter, Depends

from worktop.ai_workspace.app.ai_workspace.application.bootstrap_service import BootstrapService
from worktop.ai_workspace.app.ai_workspace.application.execution.execution_orchestrator import ExecutionOrchestrator
from worktop.ai_workspace.app.ai_workspace.application.review.review_service import ReviewService
from worktop.ai_workspace.app.ai_workspace.application.sessions.session_service import SessionService
from worktop.ai_workspace.app.ai_workspace.domain.workspace_mode import WorkspaceMode
from worktop.ai_workspace.app.ai_workspace.dto.agent_dto import AgentRunRequest, AgentRunResponse
from worktop.ai_workspace.app.ai_workspace.dto.bootstrap_dto import BootstrapDto, UserPermissionsDto, UserPreferencesDto
from worktop.ai_workspace.app.ai_workspace.dto.chat_dto import ChatMessageDto, ChatRequest, ChatResponse
from worktop.ai_workspace.app.ai_workspace.dto.execution_dto import ExecutionRunDto
from worktop.ai_workspace.app.ai_workspace.dto.mappers import execution_to_dto
from worktop.ai_workspace.app.ai_workspace.dto.model_dto import ModelCatalogDto, ModelLimitsDto, ModelMetadataDto, ModelRuntimeConfigurationDto
from worktop.ai_workspace.app.ai_workspace.dto.tool_dto import ToolCapabilitiesDto, ToolDefinitionDto, ToolRegistryDto, ToolRuntimeSelectionDto
from worktop.ai_workspace.app.common.tenancy import get_tenant_id
from worktop.ai_workspace.app.dependencies.ai_workspace_dependencies import (
    get_bootstrap_service,
    get_execution_orchestrator,
    get_review_service,
    get_session_service,
)

router = APIRouter(prefix="/ai-workspace", tags=["AI Workspace"])


@router.get("/bootstrap", response_model=BootstrapDto)
def get_bootstrap(service: BootstrapService = Depends(get_bootstrap_service)) -> BootstrapDto:
    state = service.build()
    return BootstrapDto(
        models=ModelCatalogDto(
            models=[
                ModelMetadataDto(
                    id=m.id,
                    display_name=m.display_name,
                    provider_id=m.provider_id,
                    limits=ModelLimitsDto(
                        context_window_tokens=m.limits.context_window_tokens,
                        max_output_tokens=m.limits.max_output_tokens,
                    ),
                    is_default=m.is_default,
                )
                for m in state.models.models
            ],
            runtime=ModelRuntimeConfigurationDto(selected_model_id=state.models.runtime.selected_model_id)
            if state.models.runtime
            else None,
        ),
        tools=ToolRegistryDto(
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
                for t in state.tools
            ],
            runtime=ToolRuntimeSelectionDto(enabled_tool_ids=[t.id for t in state.tools]),
        ),
        feature_flags=state.feature_flags.flags,
        permissions=UserPermissionsDto(
            can_run_agent=state.permissions.can_run_agent,
            can_apply_changes=state.permissions.can_apply_changes,
            can_edit_settings=state.permissions.can_edit_settings,
        ),
        preferences=UserPreferencesDto(),
)


def _chat_message_to_dto(message) -> ChatMessageDto:
    return ChatMessageDto(
        id=message.id,
        session_id=message.session_id,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        execution_id=message.execution_id,
    )


@router.post("/ask", response_model=ChatMessageDto)
async def ask(
    request: ChatRequest,
    orchestrator: ExecutionOrchestrator = Depends(get_execution_orchestrator),
    session_service: SessionService = Depends(get_session_service),
    tenant_id: str = Depends(get_tenant_id),
) -> ChatMessageDto:
    await orchestrator.run(request.session_id, tenant_id, WorkspaceMode.CHAT, request.prompt)
    messages = session_service.get_messages(request.session_id)
    return _chat_message_to_dto(messages[-1])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: ExecutionOrchestrator = Depends(get_execution_orchestrator),
    session_service: SessionService = Depends(get_session_service),
    tenant_id: str = Depends(get_tenant_id),
) -> ChatResponse:
    await orchestrator.run(request.session_id, tenant_id, WorkspaceMode.CHAT, request.prompt)
    messages = session_service.get_messages(request.session_id)
    return ChatResponse(message=_chat_message_to_dto(messages[-1]))


@router.post("/agent/run", response_model=ExecutionRunDto)
async def start_agent_run(
    request: AgentRunRequest,
    orchestrator: ExecutionOrchestrator = Depends(get_execution_orchestrator),
    review_service: ReviewService = Depends(get_review_service),
    tenant_id: str = Depends(get_tenant_id),
) -> ExecutionRunDto:
    execution = await orchestrator.run(request.session_id, tenant_id, WorkspaceMode.AGENT, request.prompt)
    file_changes = review_service.get_changes(execution.execution_id)
    return execution_to_dto(execution, file_changes)


@router.post("/agent", response_model=AgentRunResponse)
async def run_agent(
    request: AgentRunRequest,
    orchestrator: ExecutionOrchestrator = Depends(get_execution_orchestrator),
    review_service: ReviewService = Depends(get_review_service),
    tenant_id: str = Depends(get_tenant_id),
) -> AgentRunResponse:
    execution = await orchestrator.run(request.session_id, tenant_id, WorkspaceMode.AGENT, request.prompt)
    file_changes = review_service.get_changes(execution.execution_id)
    return AgentRunResponse(run=execution_to_dto(execution, file_changes))


@router.get("/prompts")
def list_prompts(mode: str | None = None) -> list[dict]:
    prompts = [
        {
            "id": "explain-code",
            "title": "Explain this code",
            "description": "Summarize selected files and important dependencies.",
            "body": "Explain the selected code and call out the main responsibilities.",
            "mode": "ask",
            "tags": ["understand"],
        },
        {
            "id": "small-refactor",
            "title": "Small refactor",
            "description": "Plan a low-risk refactor and propose file changes.",
            "body": "Refactor this area with minimal behavior change and explain the tradeoffs.",
            "mode": "agent",
            "tags": ["change"],
        },
    ]
    if mode in {"ask", "agent"}:
        return [prompt for prompt in prompts if prompt["mode"] in {mode, "both"}]
    return prompts


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: str) -> dict:
    for prompt in list_prompts():
        if prompt["id"] == prompt_id:
            return prompt
    return {
        "id": prompt_id,
        "title": prompt_id.replace("-", " ").title(),
        "body": "",
        "mode": "both",
        "tags": [],
    }


@router.get("/settings/preferences", response_model=UserPreferencesDto)
def get_preferences() -> UserPreferencesDto:
    return UserPreferencesDto()


@router.put("/settings/preferences", response_model=UserPreferencesDto)
def update_preferences(preferences: UserPreferencesDto) -> UserPreferencesDto:
    return preferences
