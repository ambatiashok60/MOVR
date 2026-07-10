from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.worktop_model_client_adapter import WorktopModelClientAdapter
from app.prompts.api_scenario_prompt import build_api_scenario_prompt
from app.prompts.api_test_code_prompt import build_api_test_code_prompt
from app.schemas.api_scenario import ApiScenario
from app.schemas.api_scenario_request import GenerateApiScenariosRequest
from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import (
    GeneratedTestFileOutput,
    ScenarioPlanOutput,
    TestCodeOutput,
)
from app.schemas.repo_profile import ApiEndpointCandidate, RepoProfile
from app.services.api_scenario_generation_service import ApiScenarioGenerationService
from app.services.api_test_code_generation_service import ApiTestCodeGenerationService
from app.validation.generated_file_guard import GeneratedFileGuard


def _scenario(**overrides) -> ApiScenario:
    data = {
        "api_scenario_id": "create-order-happy-path-ci",
        "scenario_name": "Create order succeeds",
        "scenario_type": "positive",
        "method": "POST",
        "endpoint": "/api/orders",
        "reason": "Deterministic contract check for CI.",
        "scenario_steps": ["Build payload", "POST /api/orders", "Verify response"],
        "assertions": ["Status is 201"],
    }
    data.update(overrides)
    return ApiScenario(**data)


def _profile(**overrides) -> RepoProfile:
    data = {
        "repo_path": "/tmp/repo",
        "endpoints": [
            ApiEndpointCandidate(
                method="POST", path="/api/orders", source_file="src/api/orders.py"
            )
        ],
    }
    data.update(overrides)
    return RepoProfile(**data)


def _code_request(**overrides) -> GenerateApiTestCodeRequest:
    data = {
        "user_story_hierarchy_id": 1,
        "api_scenario_id": "create-order-happy-path-ci",
        "scenario_name": "Create order succeeds",
        "repo_path": "/tmp/repo",
        "execution_target": ExecutionTarget.CI,
        "run_validation": False,
    }
    data.update(overrides)
    return GenerateApiTestCodeRequest(**data)


# ---------------------------------------------------------------- contracts

def test_scenario_rejects_unknown_type_and_method() -> None:
    with pytest.raises(ValidationError):
        _scenario(scenario_type="smoke")
    with pytest.raises(ValidationError):
        _scenario(method="post")


def test_generated_file_output_rejects_unknown_target() -> None:
    with pytest.raises(ValidationError):
        GeneratedTestFileOutput(
            relative_path="tests/test_x.py",
            content="assert True",
            test_target="pr",
            summary="x",
        )


# ------------------------------------------------------------------ adapter

class FakeAdapter(WorktopModelClientAdapter):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.tenant_id = 1
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def test_adapter_extracts_json_from_markdown_fence() -> None:
    adapter = FakeAdapter(
        ['Here you go:\n```json\n{"scenarios": [], "warnings": ["w"]}\n```']
    )
    output = adapter.complete_structured("plan", ScenarioPlanOutput)
    assert output.warnings == ["w"]


def test_adapter_repairs_invalid_first_response() -> None:
    adapter = FakeAdapter(
        [
            '{"scenarios": "not-a-list"}',
            '{"scenarios": [], "warnings": []}',
        ]
    )
    output = adapter.complete_structured("plan", ScenarioPlanOutput)
    assert output.scenarios == []
    assert len(adapter.prompts) == 2
    assert "repairing a previous structured LLM response" in adapter.prompts[1]


# ------------------------------------------------------------------ prompts

def test_scenario_prompt_uses_schema_contract() -> None:
    request = GenerateApiScenariosRequest(
        user_story_hierarchy_id=1,
        repo_path="/tmp/repo",
        acceptance_criteria=["Orders can be created"],
    )
    prompt = build_api_scenario_prompt(request, _profile())
    assert "JSON schema:" in prompt
    assert "ScenarioPlanOutput" in prompt
    assert "Valid response example:" in prompt
    assert '"api_scenario_id": "create-order-happy-path-ci"' in prompt


def test_code_prompt_uses_schema_contract_and_write_rules() -> None:
    prompt = build_api_test_code_prompt(_code_request(), _profile())
    assert "TestCodeOutput" in prompt
    assert "never write to application source paths" in prompt
    assert "Invalid response example (do not do this):" in prompt


# ------------------------------------------------------------ scenario guard

class FakeScenarioAgent:
    def __init__(self, output: ScenarioPlanOutput) -> None:
        self.output = output

    def generate(self, request, profile, repo_understanding=None) -> ScenarioPlanOutput:
        return self.output


def _scenario_request() -> GenerateApiScenariosRequest:
    return GenerateApiScenariosRequest(
        user_story_hierarchy_id=1, repo_path="/tmp/repo"
    )


def test_scenario_guard_drops_duplicates_and_empty_assertions() -> None:
    output = ScenarioPlanOutput(
        scenarios=[
            _scenario(),
            _scenario(scenario_name="duplicate id"),
            _scenario(api_scenario_id="no-assertions", assertions=[]),
        ]
    )
    service = ApiScenarioGenerationService(FakeScenarioAgent(output))
    result = service.generate("t1", _scenario_request(), _profile())
    assert [s.api_scenario_id for s in result.scenarios] == [
        "create-order-happy-path-ci"
    ]
    assert any("duplicate id" in w for w in result.warnings)
    assert any("no-assertions" in w for w in result.warnings)


def test_scenario_guard_flags_ungrounded_endpoint_for_review() -> None:
    output = ScenarioPlanOutput(
        scenarios=[_scenario(api_scenario_id="ghost", endpoint="/api/ghost")]
    )
    service = ApiScenarioGenerationService(FakeScenarioAgent(output))
    result = service.generate("t1", _scenario_request(), _profile())
    assert result.needs_review is True
    assert any("/api/ghost" in reason for reason in result.review_reasons)


def test_scenario_guard_keeps_grounded_scenario_clean() -> None:
    service = ApiScenarioGenerationService(
        FakeScenarioAgent(ScenarioPlanOutput(scenarios=[_scenario()]))
    )
    result = service.generate("t1", _scenario_request(), _profile())
    assert result.needs_review is False
    assert len(result.scenarios) == 1


# ---------------------------------------------------------------- file guard

JAVA_TEST = (
    "package com.acme;\n\nimport org.junit.jupiter.api.Test;\n\nclass OrderTest {\n"
    "  @Test\n  void createsOrder() {\n    assertThat(true).isTrue();\n  }\n}\n"
)


def _file(path: str, content: str = JAVA_TEST, target: str = "ci") -> GeneratedTestFileOutput:
    return GeneratedTestFileOutput(
        relative_path=path, content=content, test_target=target, summary="s"
    )


def test_file_guard_rejects_application_source_paths(tmp_path) -> None:
    guard = GeneratedFileGuard()
    output = TestCodeOutput(
        files=[_file("src/main/java/com/acme/OrderService.java")]
    )
    guarded, warnings, reasons = guard.review(
        str(tmp_path), output, _profile(), _code_request(repo_path=str(tmp_path))
    )
    assert guarded.files == []
    assert any("application source" in w for w in warnings)
    assert reasons


def test_file_guard_accepts_java_test_tree_file(tmp_path) -> None:
    guard = GeneratedFileGuard()
    output = TestCodeOutput(
        files=[_file("src/test/java/com/acme/OrderControllerTest.java")]
    )
    guarded, warnings, reasons = guard.review(
        str(tmp_path), output, _profile(), _code_request(repo_path=str(tmp_path))
    )
    assert len(guarded.files) == 1
    assert reasons == []


def test_file_guard_rejects_content_without_assertions(tmp_path) -> None:
    guard = GeneratedFileGuard()
    output = TestCodeOutput(
        files=[
            _file(
                "tests/test_orders.py",
                content="import pytest\n\ndef test_orders():\n    pass\n",
            )
        ]
    )
    guarded, warnings, _ = guard.review(
        str(tmp_path), output, _profile(), _code_request(repo_path=str(tmp_path))
    )
    assert guarded.files == []
    assert any("no assertions" in w for w in warnings)


def test_file_guard_rejects_target_mismatch(tmp_path) -> None:
    guard = GeneratedFileGuard()
    output = TestCodeOutput(
        files=[_file("src/test/java/com/acme/OrderIT.java", target="stage")]
    )
    guarded, warnings, _ = guard.review(
        str(tmp_path),
        output,
        _profile(),
        _code_request(repo_path=str(tmp_path), execution_target=ExecutionTarget.CI),
    )
    assert guarded.files == []
    assert any("test_target must be ci" in w for w in warnings)


def test_file_guard_accepts_detected_test_location(tmp_path) -> None:
    guard = GeneratedFileGuard()
    profile = _profile()
    profile.team_strategy.api_test_locations = ["qa/api-tests"]
    output = TestCodeOutput(
        files=[
            _file(
                "qa/api-tests/orders.spec.custom",
                content="check('status', 201); assert ok;",
            )
        ]
    )
    guarded, _, reasons = guard.review(
        str(tmp_path), output, profile, _code_request(repo_path=str(tmp_path))
    )
    assert len(guarded.files) == 1
    assert reasons == []


# ------------------------------------------------- service fallback on reject

class FakeCodeAgent:
    def __init__(self, output: TestCodeOutput) -> None:
        self.output = output

    def generate(self, request, profile, source_context=None, mock_stub_plan=None, repo_understanding=None):
        return self.output


def test_service_falls_back_to_strategy_skeleton_when_all_rejected(tmp_path) -> None:
    bad_output = TestCodeOutput(
        files=[_file("src/main/java/com/acme/OrderService.java")]
    )
    profile = _profile(repo_path=str(tmp_path))
    profile.team_strategy.primary_language = "python"
    service = ApiTestCodeGenerationService(FakeCodeAgent(bad_output))
    result = service.generate(
        "t1",
        _code_request(repo_path=str(tmp_path)),
        profile,
    )
    assert result.needs_review is True
    assert result.generated_files, "fallback skeleton files should be written"
    assert all("src/main" not in f.path for f in result.generated_files)
    assert any("write guard rejected" in r or "rejected" in r for r in result.review_reasons)


# --------------------------------------------------------------- phase 9

def test_scaffold_scenario_fallback_sets_needs_review() -> None:
    from app.schemas.llm_outputs import ScenarioPlanOutput

    output = ScenarioPlanOutput(
        scenarios=[_scenario()],
        warnings=["SCAFFOLD: deterministic template scenarios were used..."],
    )
    service = ApiScenarioGenerationService(FakeScenarioAgent(output))
    result = service.generate("t1", _scenario_request(), _profile())
    assert result.needs_review is True
    assert any("scaffold" in r.lower() for r in result.review_reasons)


def test_guard_accepts_path_matching_existing_test_directory(tmp_path) -> None:
    from app.schemas.repo_profile import ExistingApiTestCandidate

    guard = GeneratedFileGuard()
    profile = _profile()
    profile.existing_tests = [
        ExistingApiTestCandidate(path="custom/qa/orders_check.py")
    ]
    output = TestCodeOutput(
        files=[
            _file(
                "custom/qa/new_orders_check.py",
                content="import pytest\n\ndef test_x():\n    assert True\n",
            )
        ]
    )
    guarded, _, reasons = guard.review(
        str(tmp_path), output, profile, _code_request(repo_path=str(tmp_path))
    )
    assert len(guarded.files) == 1
    assert reasons == []


def test_discovery_agent_concludes_from_turns(tmp_path) -> None:
    from app.agents.repo_discovery_agent import RepoDiscoveryAgent

    (tmp_path / "package.json").write_text('{"name": "svc"}', encoding="utf-8")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def complete_structured(self, prompt, response_model):
            self.calls += 1
            if self.calls == 1:
                return response_model.model_validate(
                    {"requests": [{"kind": "read_file", "target": "package.json"}]}
                )
            return response_model.model_validate(
                {
                    "requests": [],
                    "understanding": {
                        "languages": ["javascript"],
                        "test_frameworks": ["jest"],
                        "test_locations": ["tests"],
                        "ci_test_command": "npm test",
                        "confidence": 0.8,
                    },
                }
            )

    agent = RepoDiscoveryAgent(llm_client=FakeLLM())
    understanding = agent.discover(str(tmp_path))
    assert understanding is not None
    assert understanding.test_frameworks == ["jest"]
    assert understanding.ci_test_command == "npm test"


def test_discovery_agent_returns_none_on_failure(tmp_path) -> None:
    from app.agents.repo_discovery_agent import RepoDiscoveryAgent

    class BrokenLLM:
        def complete_structured(self, prompt, response_model):
            raise RuntimeError("model unavailable")

    assert RepoDiscoveryAgent(llm_client=BrokenLLM()).discover(str(tmp_path)) is None


def test_prompts_render_repo_understanding() -> None:
    from app.schemas.repo_understanding import RepoUnderstanding

    understanding = RepoUnderstanding(
        languages=["kotlin"],
        test_frameworks=["kotest"],
        test_locations=["src/test/kotlin"],
        ci_test_command="./gradlew test",
        confidence=0.7,
    )
    prompt = build_api_test_code_prompt(
        _code_request(), _profile(), repo_understanding=understanding
    )
    assert "Discovered repository understanding" in prompt
    assert "kotest" in prompt
    assert "./gradlew test" in prompt
    assert "a hint only" in prompt


def test_guard_repair_loop_heals_rejected_generation(tmp_path) -> None:
    """First attempt writes to app source; the guard findings are fed back and
    the second attempt produces a safe test file — no skeleton fallback."""

    class HealingAgent:
        def __init__(self) -> None:
            self.calls = 0
            self.contexts: list[str | None] = []

        def generate(self, request, profile, source_context=None,
                     mock_stub_plan=None, repo_understanding=None):
            self.calls += 1
            self.contexts.append(request.additional_context)
            if self.calls == 1:
                return TestCodeOutput(
                    files=[_file("src/main/java/com/acme/OrderService.java")]
                )
            return TestCodeOutput(
                files=[_file("src/test/java/com/acme/OrderControllerTest.java")]
            )

    agent = HealingAgent()
    service = ApiTestCodeGenerationService(agent)
    result = service.generate(
        "t1", _code_request(repo_path=str(tmp_path)), _profile(repo_path=str(tmp_path))
    )

    assert agent.calls == 2
    assert "REJECTED BY THE WRITE GUARD" in (agent.contexts[1] or "")
    assert [f.path for f in result.generated_files] == [
        "src/test/java/com/acme/OrderControllerTest.java"
    ]
    assert any("Self-healing succeeded" in w for w in result.warnings)


# --------------------------------------------------------------- phase 10

def test_scenario_agent_explores_then_concludes(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "orders.py").write_text("def create(): ...", encoding="utf-8")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def complete_structured(self, prompt, response_model):
            self.calls += 1
            if self.calls == 1:
                return response_model.model_validate(
                    {"requests": [{"kind": "read_file", "target": "src/orders.py"}]}
                )
            assert "def create()" in prompt  # evidence was fed back
            return response_model.model_validate(
                {"requests": [], "output": {"scenarios": [], "warnings": ["explored"]}}
            )

    from app.agents.scenario_agent import ScenarioAgent

    agent = ScenarioAgent(llm_client=FakeLLM())
    output = agent.generate(
        GenerateApiScenariosRequest(
            user_story_hierarchy_id=1, repo_path=str(tmp_path)
        ),
        _profile(repo_path=str(tmp_path)),
    )
    # empty scenarios -> falls back to scaffold, but the loop itself ran both turns
    assert agent.llm.calls == 2


def test_stage_scenario_downgraded_without_stage_infra() -> None:
    output = ScenarioPlanOutput(
        scenarios=[_scenario(execution_target=ExecutionTarget.STAGE)]
    )
    service = ApiScenarioGenerationService(FakeScenarioAgent(output))
    result = service.generate("t1", _scenario_request(), _profile())
    assert result.scenarios[0].execution_target == ExecutionTarget.CI
    assert any("stage" in r.lower() for r in result.review_reasons)


def test_stage_scenario_kept_when_stage_infra_exists() -> None:
    profile = _profile()
    profile.team_strategy.stage_command = "mvn verify -Pstage"
    output = ScenarioPlanOutput(
        scenarios=[_scenario(execution_target=ExecutionTarget.STAGE)]
    )
    service = ApiScenarioGenerationService(FakeScenarioAgent(output))
    result = service.generate("t1", _scenario_request(), profile)
    assert result.scenarios[0].execution_target == ExecutionTarget.STAGE


def test_mock_emission_gap_flagged(tmp_path) -> None:
    from app.schemas.mock_stub_plan import MockStubPlan

    guard = GeneratedFileGuard()
    plan = MockStubPlan.model_validate(
        {"dependencies_to_mock": [{"name": "PaymentClient", "dependency_kind": "client",
                                   "source_file": "src/x.java", "reason": "downstream"}]}
    )
    unmocked = TestCodeOutput(
        files=[_file("src/test/java/com/acme/OrderControllerTest.java")]
    )
    _, warnings, reasons = guard.review(
        str(tmp_path), unmocked, _profile(), _code_request(repo_path=str(tmp_path)),
        mock_stub_plan=plan,
    )
    assert any("Mock emission gap" in r for r in reasons)

    mocked = TestCodeOutput(
        files=[_file(
            "src/test/java/com/acme/OrderControllerTest.java",
            content=JAVA_TEST.replace("class OrderTest {", "@MockBean PaymentClient pc;\nclass OrderTest {"),
        )]
    )
    _, _, reasons2 = guard.review(
        str(tmp_path), mocked, _profile(), _code_request(repo_path=str(tmp_path)),
        mock_stub_plan=plan,
    )
    assert not any("Mock emission gap" in r for r in reasons2)


def test_mock_emission_gap_triggers_healing_regeneration(tmp_path) -> None:
    from app.schemas.mock_stub_plan import MockStubPlan

    plan = MockStubPlan.model_validate(
        {"dependencies_to_mock": [{"name": "PaymentClient", "dependency_kind": "client",
                                   "source_file": "src/x.java", "reason": "downstream"}]}
    )

    class HealingMockAgent:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request, profile, source_context=None,
                     mock_stub_plan=None, repo_understanding=None):
            self.calls += 1
            if self.calls == 1:  # safe file but no mocks
                return TestCodeOutput(
                    files=[_file("src/test/java/com/acme/OrderControllerTest.java")]
                )
            return TestCodeOutput(  # healed: mocks the dependency
                files=[_file(
                    "src/test/java/com/acme/OrderControllerTest.java",
                    content=JAVA_TEST.replace(
                        "class OrderTest {", "@MockBean PaymentClient pc;\nclass OrderTest {"
                    ),
                )]
            )

    agent = HealingMockAgent()
    service = ApiTestCodeGenerationService(agent)
    result = service.generate(
        "t1", _code_request(repo_path=str(tmp_path)),
        _profile(repo_path=str(tmp_path)), mock_stub_plan=plan,
    )
    assert agent.calls == 2  # gap forced a regeneration round
    assert not any("Mock emission gap" in r for r in result.review_reasons)
