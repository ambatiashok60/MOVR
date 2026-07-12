from __future__ import annotations

from typing import Any, TypeVar

try:
    from worktop.core_services.app.models.llm_telemetry import (
        TelemetryFeature,
        TelemetrySubFeature,
    )
    from worktop.core_services.app.services.llm_telemetry_service import trace_llm

    _TELEMETRY_AVAILABLE = True
except ImportError:
    trace_llm = None
    TelemetryFeature = None
    TelemetrySubFeature = None
    _TELEMETRY_AVAILABLE = False

from worktop.core_services.app.utility.custom_logger.logging import logger

ResponseModel = TypeVar("ResponseModel")

__all__ = ["BaseAgent", "logger"]


class BaseAgent:
    agent_name = "base_agent"

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client

    def log_start(self, stage: str, **metadata: Any) -> dict[str, Any]:
        context = {
            key: value
            for key, value in {
                "stage": stage,
                "agent_name": self.agent_name,
                **metadata,
            }.items()
            if value is not None
        }
        logger.info(
            "[playwright-generation] agent=%s stage=%s status=started context=%s",
            self.agent_name,
            stage,
            context,
        )
        return context

    def log_decision(self, title: str, message: str, **metadata: Any) -> None:
        logger.info(
            "[playwright-generation] decision=%s message=%s metadata=%s",
            title,
            message,
            metadata,
        )

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        if self.llm is None:
            raise RuntimeError(
                "LLM client is required for this agentic Playwright generation "
                "process. Fast-failing because no real model client is available."
            )
        try:
            return self.llm.complete_structured(prompt=prompt, response_model=response_model)
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=llm_structured_completion status=failed error=%s",
                self.agent_name,
                exc,
            )
            raise


    def complete_with_exploration(
        self,
        base_prompt: str,
        turn_model: type[ResponseModel],
        repo_path: str,
        max_turns: int = 4,
        max_requests_per_turn: int = 4,
    ) -> ResponseModel:
        """Agentic tool loop: gather repo evidence, state reasoning, then conclude.

        Each turn the model must explain its reasoning and either request
        evidence (read_file/search/list_dir, sandboxed) or return the final
        decision. Every request carries a reason; everything is logged so the
        decision trail is reconstructable at all levels.
        """
        from worktop.test_agent.app.prompts.prompt_sections import response_contract
        from worktop.test_agent.app.tools.repo_explorer_tool import RepoExplorer

        explorer = RepoExplorer(repo_path)
        transcript: list[str] = []
        for turn_index in range(max_turns):
            final = turn_index == max_turns - 1
            closing = (
                "This is your final turn: you MUST return `output` now, with your reasoning."
                if final
                else "State `reasoning`, then request evidence via `requests` or return `output`."
            )
            evidence = "\n\n".join(transcript[-16:]) or "(none gathered yet)"
            prompt = (
                f"{base_prompt}\n\nEvidence gathered from the repository so far:\n"
                f"{evidence}\n\n{closing}\n\n{response_contract(turn_model)}"
            )
            turn = self.complete_structured(prompt, turn_model)
            logger.info(
                "[playwright-generation] agent=%s stage=exploration turn=%s concluded=%s "
                "reasoning=%s requests=%s",
                self.agent_name,
                turn_index + 1,
                turn.output is not None,
                (turn.reasoning or "unstated")[:400],
                [f"{r.kind}:{r.target}" for r in turn.requests][:8],
            )
            if turn.output is not None:
                return turn.output
            if not turn.requests:
                break
            charge_repository_read = getattr(self.llm, "charge_repository_read", None)
            for request in turn.requests[:max_requests_per_turn]:
                if charge_repository_read is not None:
                    charge_repository_read()
                transcript.append(explorer.execute(request))
        raise RuntimeError(f"{self.agent_name} exploration ended without output")
