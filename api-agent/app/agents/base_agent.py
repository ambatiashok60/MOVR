from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.llm_client import LLMClient
from app.utils.logging_utils import build_log_context, log_exception, log_step

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class BaseAgent:
    agent_name = "base_agent"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client

    def log_start(self, stage: str, **metadata: Any) -> dict[str, Any]:
        context = build_log_context(stage=stage, agent_name=self.agent_name, **metadata)
        log_step(f"{self.agent_name}_started", context)
        return context

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        if self.llm is None:
            raise RuntimeError("LLM client is required for API agent generation")
        try:
            return self.llm.complete_structured(prompt=prompt, response_model=response_model)
        except Exception as exc:
            log_exception(
                exc,
                context={"stage": "llm_structured_completion", "agent": self.agent_name},
            )
            raise


    def complete_with_exploration(
        self,
        base_prompt: str,
        turn_model: type[ResponseModel],
        repo_path: str,
        max_turns: int = 4,
        max_requests_per_turn: int = 4,
    ):
        """Agentic tool loop: the model gathers repo evidence before concluding.

        Each turn the model either returns `requests` (read_file / search /
        list_dir, executed sandboxed via RepoExplorer) or a final `output`.
        Static one-shot calls guess; this lets the model verify field names,
        existing coverage, and idioms first.
        """
        from app.prompts.prompt_sections import response_contract
        from app.tools.path_safety import resolve_workspace_path
        from app.tools.repo_explorer import RepoExplorer

        explorer = RepoExplorer()
        root = resolve_workspace_path(repo_path)
        transcript: list[str] = []
        for turn_index in range(max_turns):
            final = turn_index == max_turns - 1
            closing = (
                "This is your final turn: you MUST return `output` now."
                if final
                else "Request repo evidence via `requests`, or return `output` once confident."
            )
            evidence = "\n\n".join(transcript[-16:]) or "(none gathered yet)"
            prompt = (
                f"{base_prompt}\n\nEvidence gathered from the repository so far:\n"
                f"{evidence}\n\n{closing}\n\n{response_contract(turn_model)}"
            )
            turn = self.complete_structured(prompt, turn_model)
            if turn.output is not None:
                log_step(
                    f"{self.agent_name}_exploration_concluded",
                    {"turns": turn_index + 1},
                )
                return turn.output
            if not turn.requests:
                break
            for request in turn.requests[:max_requests_per_turn]:
                transcript.append(explorer.execute(root, request))
        raise RuntimeError(
            f"{self.agent_name} exploration loop ended without producing output"
        )
