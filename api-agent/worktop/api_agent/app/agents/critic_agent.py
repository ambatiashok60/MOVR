from __future__ import annotations

from worktop.api_agent.app.agents.base_agent import BaseAgent
from worktop.api_agent.app.prompts.critic_review_prompt import build_critic_review_prompt
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext


class CriticAgent(BaseAgent):
    """Second model pass over generated tests before anything touches disk
    (test_agent critic_review parity). Consumes and produces the same
    ``TestCodeOutput`` artifact so generation, critique, and repair compose."""

    agent_name = "critic_agent"

    def review(
        self,
        output: TestCodeOutput,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context: GenerationSourceContext | None = None,
        mock_stub_plan=None,
        repo_understanding=None,
        validation_failure: str | None = None,
    ) -> TestCodeOutput:
        self.log_start("critic_review", file_count=len(output.files))
        prompt = build_critic_review_prompt(
            output,
            request,
            profile,
            source_context=source_context,
            mock_stub_plan=mock_stub_plan,
            repo_understanding=repo_understanding,
            validation_failure=validation_failure,
        )
        return self.complete_structured(prompt, TestCodeOutput)
