from app.ai_workspace.application.prompts.prompt_builder_service import StructuredPrompt
from app.ai_workspace.domain.workspace_mode import WorkspaceMode

_CHAT_SYSTEM_PROMPT = (
    "You are AI Workspace's Ask mode assistant. Answer questions about the given repository "
    "context. You have no ability to modify files — never claim to have made a change."
)

# V1 simplification: a real per-step tool-calling agent loop (LLM calls read_file, gets a
# result, decides the next call, ...) needs confirmed function-calling support from the
# existing LLM client, which is NOT confirmed — see
# app/integrations/existing_model_client/README.md. Until that's confirmed, Agent mode asks
# for one structured JSON response containing the full plan AND full proposed file content in
# a single call. agent_service.py parses this directly; it does not dispatch tool calls back
# through ToolExecutionService for file writes (read-context tools already ran during context
# building). This is a real, working V1 behavior — not a stub — but it is a materially
# different (and less capable) design than true iterative tool-calling, and should be revisited
# once function-calling support is confirmed.
_AGENT_SYSTEM_PROMPT = (
    "You are AI Workspace's Agent mode assistant. Given a task and repository context, respond "
    "with ONLY a single JSON object (no prose, no markdown fences) matching this shape:\n"
    "{\n"
    '  "plan": {"steps": [{"description": str, "affected_files": [str], "confidence": float}]},\n'
    '  "file_changes": [{"path": str, "status": "added"|"modified"|"deleted", "new_content": str}]\n'
    "}\n"
    "new_content must be the COMPLETE proposed file content, not a diff or partial snippet. "
    "Only include files that actually need to change."
)


class PromptRenderer:
    """Turns a StructuredPrompt into the system_prompt/user_prompt strings that
    DefaultLLMClientAdapter passes into the existing model client. This is the one place prompt wording
    lives — ask_mode / agent_mode differ in system prompt text (including, for agent mode, the
    required JSON response contract), not in how context is assembled (that's
    ContextBuilderService/PromptBuilderService, shared by both)."""

    def render(self, prompt: StructuredPrompt) -> tuple[str, str]:
        system_prompt = _AGENT_SYSTEM_PROMPT if prompt.mode == WorkspaceMode.AGENT else _CHAT_SYSTEM_PROMPT
        user_prompt = self._render_user_prompt(prompt)
        return system_prompt, user_prompt

    def _render_user_prompt(self, prompt: StructuredPrompt) -> str:
        sections: list[str] = []

        if prompt.context_files:
            file_blocks = "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in prompt.context_files)
            sections.append(f"## Repository context\n{file_blocks}")

        if prompt.recent_conversation:
            history = "\n".join(f"{role}: {content}" for role, content in prompt.recent_conversation)
            sections.append(f"## Recent conversation\n{history}")

        sections.append(f"## Task\n{prompt.task}")
        return "\n\n".join(sections)
