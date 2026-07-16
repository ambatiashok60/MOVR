from __future__ import annotations

from worktop.api_agent.app.agents.base_agent import BaseAgent
from worktop.api_agent.app.config import settings
from worktop.api_agent.app.prompts.test_placement_prompt import build_test_placement_prompt
from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.schemas.test_placement import TestPlacementOutput, TestPlacementTurn


class TestPlacementAgent(BaseAgent):
    """Decides create-new vs extend-existing for each generated test file.

    Runs the same agentic exploration loop as discovery/generation so the
    model reads the actual target files before producing a merge — placement
    from memory is how existing coverage gets clobbered.
    """

    __test__ = False  # prevent pytest collection

    agent_name = "test_placement_agent"

    def place(
        self,
        output: TestCodeOutput,
        profile: RepoProfile,
        repo_path: str,
        source_context: GenerationSourceContext | None = None,
        repo_understanding=None,
    ) -> TestPlacementOutput:
        self.log_start("test_placement", file_count=len(output.files))
        prompt = build_test_placement_prompt(
            output,
            profile,
            source_context=source_context,
            repo_understanding=repo_understanding,
        )
        return self.complete_with_exploration(
            prompt,
            TestPlacementTurn,
            repo_path,
            max_turns=max(settings.test_placement_max_turns, 1),
        )
