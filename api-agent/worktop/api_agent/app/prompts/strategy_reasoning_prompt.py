from __future__ import annotations

import json

from worktop.api_agent.app.prompts.prompt_sections import response_contract
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.strategy_reasoning import StrategyReasoningOutput


def build_strategy_reasoning_prompt(profile: RepoProfile) -> str:
    assessment = profile.capability_assessment
    plan = profile.generation_plan
    if assessment is None or plan is None:
        raise ValueError("Capability assessment and deterministic generation plan are required")
    allowed = [item.strategy_name for item in plan.candidates]
    evidence = [
        {"evidence_id": item.evidence_id, "capability": item.capability, "type": item.evidence_type.value, "source_file": item.source_file, "line": item.start_line, "signal": item.signal, "confidence": item.confidence}
        for item in assessment.evidence[:120]
    ]
    candidates = [item.model_dump(mode="json") for item in plan.candidates]
    return f"""
You are reviewing a deterministic API-test strategy decision. You may confirm it,
request more repository evidence, require review, or declare it unsupported.

Security and correctness rules:
- Select only from ALLOWED_STRATEGIES. Never invent a framework or dependency.
- Cite only EVIDENCE_IDS present below. Never invent a file, symbol, command, or test.
- Existing tests outrank build dependencies; source usage outranks generic defaults.
- Missing critical evidence must produce needs_more_evidence or needs_review.
- Do not recommend REST drivers for GraphQL or gRPC.
- Do not recommend MockMvc for a purely reactive WebFlux endpoint.
- A new dependency or infrastructure mechanism requires review.

ALLOWED_STRATEGIES:
{json.dumps(allowed)}

DETERMINISTIC_PLAN:
{plan.model_dump_json(indent=2)}

CAPABILITY_TOPOLOGY:
{assessment.topology.model_dump_json(indent=2)}

EVIDENCE:
{json.dumps(evidence, indent=2)}

CANDIDATES:
{json.dumps(candidates, indent=2)}

{response_contract(StrategyReasoningOutput)}
""".strip()
