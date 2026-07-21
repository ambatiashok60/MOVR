"""Critic review stage (test_agent critic_review parity): a second model pass
over generated tests that can revise files but never lose them."""

from __future__ import annotations

import pytest

from worktop.api_agent.app.agents.test_generation_agent import (
    TestGenerationAgent as GenerationAgent,
)
from worktop.api_agent.app.config import settings
from worktop.api_agent.app.governance.generation_budget import BudgetExceededError
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
)
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import (
    GeneratedTestFileOutput,
    TestCodeOutput,
)
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.services.api_test_code_generation_service import (
    ApiTestCodeGenerationService,
)


def _request(**overrides) -> GenerateApiTestCodeRequest:
    data = {
        "user_story_hierarchy_id": 1,
        "api_scenario_id": "create-order-happy-path-ci",
        "scenario_name": "Create order succeeds",
        "scenario_steps": ["POST a valid order", "Verify 201"],
        "repo_path": "/tmp/repo",
        "execution_target": ExecutionTarget.CI,
        "run_validation": False,
    }
    data.update(overrides)
    return GenerateApiTestCodeRequest(**data)


def _output(content: str = "def test_create_order():\n    assert True\n") -> TestCodeOutput:
    return TestCodeOutput(
        files=[
            GeneratedTestFileOutput(
                relative_path="tests/test_orders.py",
                content=content,
                test_target="ci",
                summary="Order creation coverage",
            )
        ]
    )


class _StubCritic:
    def __init__(self, result: TestCodeOutput | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls = 0

    def review(self, output, request, profile, **kwargs):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result if self._result is not None else output


def _service(critic) -> ApiTestCodeGenerationService:
    return ApiTestCodeGenerationService(GenerationAgent(None), critic=critic)


PROFILE = RepoProfile(repo_path="/tmp/repo")


class TestCriticReview:
    def test_revision_is_adopted_and_flagged(self):
        revised = _output("def test_create_order():\n    assert response.status_code == 201\n")
        critic = _StubCritic(result=revised)
        reviewed, warnings = _service(critic)._critic_review(
            _output(), _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed.files[0].content == revised.files[0].content
        assert any("revised 1 generated file" in warning for warning in warnings)
        assert critic.calls == 1

    def test_unchanged_review_adds_no_warnings(self):
        output = _output()
        reviewed, warnings = _service(_StubCritic(result=output))._critic_review(
            output, _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed.files == output.files
        assert warnings == []

    def test_critic_failure_keeps_original_files(self):
        output = _output()
        reviewed, warnings = _service(_StubCritic(error=RuntimeError("llm down")))._critic_review(
            output, _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed.files == output.files
        assert any("Critic review failed" in warning for warning in warnings)

    def test_critic_cannot_drop_or_rename_files(self):
        dropped = TestCodeOutput(files=[])
        reviewed, warnings = _service(_StubCritic(result=dropped))._critic_review(
            _output(), _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert len(reviewed.files) == 1
        assert any("changed the generated file set" in warning for warning in warnings)

        renamed = _output()
        renamed.files[0].relative_path = "tests/test_other.py"
        reviewed, warnings = _service(_StubCritic(result=renamed))._critic_review(
            _output(), _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed.files[0].relative_path == "tests/test_orders.py"
        assert any("changed the generated file set" in warning for warning in warnings)

    def test_budget_exhaustion_propagates(self):
        from worktop.api_agent.app.governance.generation_budget import BudgetReport

        error = BudgetExceededError("llm_calls", BudgetReport())
        with pytest.raises(BudgetExceededError):
            _service(_StubCritic(error=error))._critic_review(
                _output(), _request(), PROFILE, None, None, None, stage="critic_review"
            )

    def test_disabled_critic_is_never_called(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_critic_review", False)
        critic = _StubCritic()
        output = _output()
        reviewed, warnings = _service(critic)._critic_review(
            output, _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed is output
        assert warnings == [] and critic.calls == 0

    def test_no_llm_and_no_critic_skips_quietly(self):
        service = ApiTestCodeGenerationService(GenerationAgent(None))
        output = _output()
        reviewed, warnings = service._critic_review(
            output, _request(), PROFILE, None, None, None, stage="critic_review"
        )
        assert reviewed is output
        assert warnings == []
