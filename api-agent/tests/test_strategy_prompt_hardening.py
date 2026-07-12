from pathlib import Path

import pytest
from pydantic import ValidationError

from worktop.api_agent.app.prompts.strategy_reasoning_prompt import build_strategy_reasoning_prompt
from worktop.api_agent.app.schemas.strategy_reasoning import StrategyReasoningOutput
from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService
from worktop.api_agent.app.services.strategy_reasoning_service import StrategyReasoningService


def _profile(root: Path):
    (root / "build.gradle").write_text("spring-boot-starter-webflux junit-jupiter mockwebserver")
    source = root / "src/main/java/Client.java"; source.parent.mkdir(parents=True); source.write_text("class Client { WebClient client; reactor.core.publisher.Mono<String> call() { return null; } }")
    test = root / "src/test/java/ClientTest.java"; test.parent.mkdir(parents=True); test.write_text("class ClientTest { WebTestClient web; MockWebServer server; }")
    return ApiRepoContextService().build(str(root))


def test_strategy_reasoning_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        StrategyReasoningOutput.model_validate({"decision": "confirm", "selected_strategy": "x", "confidence": 0.8, "evidence_ids": [], "reasons": ["x"], "rejected_alternatives": [], "unresolved_questions": [], "recommended_next_stage": "dependency_planning", "invented": True})


def test_strategy_prompt_contains_pydantic_schema_and_allowed_candidates(tmp_path: Path) -> None:
    prompt = build_strategy_reasoning_prompt(_profile(tmp_path))
    assert "StrategyReasoningOutput" in prompt
    assert "JSON schema:" in prompt
    assert "ALLOWED_STRATEGIES" in prompt
    assert "java_spring_webtestclient" in prompt
    assert "Never invent" in prompt


class FakeReasoningAgent:
    def __init__(self, output): self.output = output
    def review(self, profile): return self.output


def test_reasoning_cannot_select_unregistered_strategy_or_unknown_evidence(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    output = StrategyReasoningOutput(decision="confirm", selected_strategy="invented_strategy", confidence=0.99, evidence_ids=["ev-not-real"], reasons=["invented"], recommended_next_stage="dependency_planning")
    reviewed = StrategyReasoningService().review(profile, FakeReasoningAgent(output))
    assert reviewed is not None
    assert reviewed.decision == "needs_review"
    assert reviewed.selected_strategy == "java_spring_webtestclient"
    assert reviewed.evidence_ids == []
    assert profile.generation_plan is not None and profile.generation_plan.status == "needs_review"


def test_detector_telemetry_is_attached_and_cache_is_visible(tmp_path: Path) -> None:
    first = _profile(tmp_path).capability_assessment
    second = ApiRepoContextService().build(str(tmp_path)).capability_assessment
    assert first is not None and first.telemetry is not None
    assert first.telemetry.detector_runs
    assert first.telemetry.evidence_count == len(first.evidence)
    assert second is not None and second.cache_hit is True
    assert second.telemetry is not None and second.telemetry.cache_hit is True
