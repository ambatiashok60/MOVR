from app.ai_workspace.application.context.context_builder_service import ContextBuilderService
from app.ai_workspace.application.prompts.prompt_builder_service import PromptBuilderService
from app.ai_workspace.application.prompts.prompt_renderer import PromptRenderer
from app.ai_workspace.application.sessions.session_service import SessionService
from app.ai_workspace.domain.chat_message import ChatRole
from app.ai_workspace.domain.execution_context import ExecutionContext, ExecutionStage, ExecutionStageStatus
from app.llm.application.llm_application_service import LLMApplicationService
from app.utils.logging_utils import build_log_context, log_step

_STAGE_CONTEXT = "build_context"
_STAGE_LLM = "llm_completion"


class ChatService:
    """Implements ExecutionOrchestrator's ExecutionStrategy for Ask mode. Read-only by
    construction — it has no ToolExecutionService dependency at all, so there is no code path
    here that could write a file even by mistake. No tool-calling loop either: this is a
    single context-build -> single LLM call -> response, matching 'Chat Mode answers only'.
    A multi-turn tool-calling Ask mode is future work, gated on confirming the existing LLM
    client actually supports function calling (unconfirmed — see
    app/integrations/existing_model_client/README.md)."""

    def __init__(
        self,
        context_builder: ContextBuilderService,
        prompt_builder: PromptBuilderService,
        prompt_renderer: PromptRenderer,
        llm_service: LLMApplicationService,
        session_service: SessionService,
    ):
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder
        self._prompt_renderer = prompt_renderer
        self._llm_service = llm_service
        self._session_service = session_service

    async def run(self, execution: ExecutionContext, runtime) -> None:
        log_step(
            "ai_workspace_chat_started",
            build_log_context(
                session_id=execution.session_id,
                execution_id=execution.execution_id,
                workspace_path=runtime.workspace_path,
                stage="chat",
            ),
        )
        self._session_service.record_message(execution.session_id, ChatRole.USER, execution.prompt)

        execution.stages.append(ExecutionStage(id=_STAGE_CONTEXT, label="Building context", status=ExecutionStageStatus.ACTIVE))
        context = self._context_builder.build(runtime)
        execution.stages[-1].status = ExecutionStageStatus.DONE

        execution.stages.append(ExecutionStage(id=_STAGE_LLM, label="Generating response", status=ExecutionStageStatus.ACTIVE))
        structured_prompt = self._prompt_builder.build(runtime.mode, execution.prompt, context)
        system_prompt, user_prompt = self._prompt_renderer.render(structured_prompt)
        completion = self._llm_service.complete(execution.execution_id, system_prompt, user_prompt)
        execution.stages[-1].status = ExecutionStageStatus.DONE

        self._session_service.record_message(
            execution.session_id, ChatRole.ASSISTANT, completion.text, execution_id=execution.execution_id
        )
        log_step(
            "ai_workspace_chat_completed",
            build_log_context(session_id=execution.session_id, execution_id=execution.execution_id, stage="chat"),
        )
