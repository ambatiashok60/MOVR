from __future__ import annotations

from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.prompts.prompt_sections import response_contract
from app.schemas.repo_understanding import DiscoveryTurn, RepoUnderstanding
from app.tools.path_safety import resolve_workspace_path
from app.tools.repo_explorer import RepoExplorer
from app.utils.logging_utils import log_exception, log_step

MAX_TURNS = 6
MAX_REQUESTS_PER_TURN = 4
MAX_FILE_CHARS = 6000
MAX_SEARCH_HITS = 20
MAX_DIR_ENTRIES = 50
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
}


class RepoDiscoveryAgent(BaseAgent):
    """Model-directed repository discovery, Claude Code / Codex style.

    Instead of pre-baked scanners deciding what the model sees, the model
    explores: each turn it requests read_file / search / list_dir actions, we
    execute them (bounded and sandboxed to the repo), feed results back, and
    repeat until it emits a RepoUnderstanding or the budget runs out. Works for
    any language or test stack because nothing framework-specific is assumed.
    """

    agent_name = "repo_discovery_agent"

    def discover(self, repo_path: str) -> RepoUnderstanding | None:
        self.log_start("repo_discovery", repo_path=repo_path)
        try:
            root = resolve_workspace_path(repo_path)
        except Exception as exc:
            log_exception(exc, context={"stage": "repo_discovery", "repo_path": repo_path})
            return None

        transcript: list[str] = [self._initial_observation(root)]
        for turn_index in range(MAX_TURNS):
            try:
                turn = self.complete_structured(
                    self._build_prompt(transcript, final_turn=turn_index == MAX_TURNS - 1),
                    DiscoveryTurn,
                )
            except Exception as exc:
                log_exception(exc, context={"stage": "repo_discovery", "turn": turn_index})
                return None
            if turn.understanding is not None:
                log_step(
                    "repo_discovery_concluded",
                    {"turns": turn_index + 1, "confidence": turn.understanding.confidence},
                )
                return turn.understanding
            if not turn.requests:
                break
            for request in turn.requests[:MAX_REQUESTS_PER_TURN]:
                transcript.append(self._execute(root, request))

        log_step("repo_discovery_budget_exhausted", {"turns": MAX_TURNS})
        return None

    def _build_prompt(self, transcript: list[str], final_turn: bool) -> str:
        observations = "\n\n".join(transcript[-24:])
        closing = (
            "This is your final turn: you MUST return `understanding` now, based "
            "on the evidence gathered so far."
            if final_turn
            else (
                "Request more evidence with `requests`, or return `understanding` "
                "once you know the repository's real testing conventions."
            )
        )
        return f"""
You are exploring a repository to understand how its API tests are actually
written and run. Do not assume any particular language or framework — conclude
only from evidence you have read.

Investigate: languages, service frameworks, test frameworks, where API tests
live, how they are executed in CI vs against a deployed stage environment,
naming/style conventions, and the best existing test files to use as examples.

{closing}

Evidence so far:
{observations}

{response_contract(DiscoveryTurn)}
""".strip()

    def _initial_observation(self, root: Path) -> str:
        return f"### list_dir .\n{self._explorer.list_dir(root, '.')}"

    def _execute(self, root: Path, request) -> str:
        return self._explorer.execute(root, request)

    @property
    def _explorer(self) -> RepoExplorer:
        if not hasattr(self, "_explorer_instance"):
            self._explorer_instance = RepoExplorer()
        return self._explorer_instance
