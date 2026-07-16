from dataclasses import dataclass, field

from worktop.ai_workspace.app.ai_workspace.application.context.context_builder_service import ContextBundle
from worktop.ai_workspace.app.ai_workspace.domain.workspace_mode import WorkspaceMode


@dataclass
class StructuredPrompt:
    """Provider-agnostic intermediate representation — prompt_renderer.py is the only thing
    that turns this into actual system/user prompt strings, so provider-specific formatting
    quirks never leak into this layer."""

    mode: WorkspaceMode
    task: str
    context_files: list[tuple[str, str]] = field(default_factory=list)  # (path, content)
    recent_conversation: list[tuple[str, str]] = field(default_factory=list)  # (role, content)
    repository_memory: str = ""


class PromptBuilderService:
    def __init__(self, memory_service=None):
        self._memory_service = memory_service
    def build(self, mode: WorkspaceMode, task: str, context: ContextBundle) -> StructuredPrompt:
        return StructuredPrompt(
            mode=mode,
            task=task,
            context_files=[(f.path, f.content) for f in context.files],
            recent_conversation=[(m.role.value, m.content) for m in context.recent_messages],
            repository_memory=self._memory_service.load(context.workspace_path) if self._memory_service else "",
        )
