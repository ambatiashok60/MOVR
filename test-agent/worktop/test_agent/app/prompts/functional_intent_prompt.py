from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import as_json, response_contract
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.generation_request import GenerationRequest


def build_functional_intent_prompt(request: GenerationRequest) -> str:
    return f"""
You are extracting functional test intent for Playwright generation.

Input request:
{as_json(request)}

Identify the business capability, actor, user journey, state transitions, and assertions.

{response_contract(FunctionalIntent)}
"""
