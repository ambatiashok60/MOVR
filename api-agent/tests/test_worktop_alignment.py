"""Worktop / test_agent parity: test-case-row payload, server-side repository
resolution, tenant security fallbacks, and coverage-preserving placement of
generated tests into existing test files."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from worktop.api_agent.app.api.security import resolve_tenant, validate_job_tenant
from worktop.api_agent.app.config import settings
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestsRequest,
)
from worktop.api_agent.app.schemas.llm_outputs import (
    GeneratedTestFileOutput,
    TestCodeOutput,
)
from worktop.api_agent.app.schemas.repo_profile import (
    ExistingApiTestCandidate,
    RepoProfile,
)
from worktop.api_agent.app.schemas.test_placement import (
    TestPlacementDecision,
    TestPlacementOutput,
)
from worktop.api_agent.app.services.repository_resolution_service import (
    resolve_repository_path,
)
from worktop.api_agent.app.services.test_placement_service import TestPlacementService
from worktop.api_agent.app.task_managers.api_test_generation_task_manager import (
    task_manager,
)

EXISTING_TEST = """import pytest
from fastapi.testclient import TestClient


def test_create_order_returns_201(client):
    response = client.post("/api/orders", json={"sku": "A1"})
    assert response.status_code == 201


def test_create_order_rejects_empty_payload(client):
    response = client.post("/api/orders", json={})
    assert response.status_code == 422
"""

NEW_TEST_BODY = """

def test_create_order_requires_auth(client):
    response = client.post("/api/orders", json={"sku": "A1"}, headers={})
    assert response.status_code == 401
"""


def _row_request(**overrides) -> GenerateApiTestsRequest:
    data = {
        "user_story_hierarchy_id": 7,
        "testcase_id": "TC-101",
        "testcase_steps": ["POST a valid order", "Verify 201 and order id"],
    }
    data.update(overrides)
    return GenerateApiTestsRequest(**data)


class _StubPlacementAgent:
    def __init__(self, output: TestPlacementOutput | None = None, error: Exception | None = None):
        self._output = output
        self._error = error

    def place(self, output, profile, repo_path, source_context=None, repo_understanding=None):
        if self._error is not None:
            raise self._error
        return self._output


def _generated_output() -> TestCodeOutput:
    return TestCodeOutput(
        files=[
            GeneratedTestFileOutput(
                relative_path="tests/test_create_order_auth.py",
                content="def test_create_order_requires_auth():\n    assert True\n",
                test_target="ci",
                summary="Auth coverage for order creation",
            )
        ]
    )


def _profile_with_existing(repo_path: str) -> RepoProfile:
    return RepoProfile(
        repo_path=repo_path,
        existing_tests=[ExistingApiTestCandidate(path="tests/test_orders.py")],
    )


class TestTestCaseRowPayload:
    def test_payload_no_longer_requires_repo_path(self):
        request = _row_request()
        assert request.repo_path is None
        assert request.to_code_request().repo_path is None

    def test_enqueue_rejects_unresolved_repo_path(self):
        with pytest.raises(ValueError, match="repo_path was not resolved"):
            task_manager.enqueue_api_tests(_row_request())

    def test_row_fields_flow_into_code_request(self):
        request = _row_request(
            repo_path="/tmp/repo",
            setup_steps=["Authenticate as admin"],
            testcase_name="Order creation",
        )
        code_request = request.to_code_request()
        assert code_request.repo_path == "/tmp/repo"
        assert code_request.scenario_name == "Order creation"
        assert code_request.scenario_steps[0] == "Authenticate as admin"


class TestServerSideRepositoryResolution:
    def test_falls_back_to_payload_when_no_datasource(self):
        assert resolve_repository_path(None, "/tmp/repo") == "/tmp/repo"

    def test_falls_back_to_settings_default(self, monkeypatch):
        monkeypatch.setattr(settings, "default_repo_path", "/srv/checkout")
        assert resolve_repository_path(None, None) == "/srv/checkout"

    def test_unresolvable_repo_path_is_a_400(self):
        with pytest.raises(HTTPException) as excinfo:
            resolve_repository_path(None, None)
        assert excinfo.value.status_code == 400


class TestTenantSecurity:
    def test_standalone_falls_back_to_payload_tenant(self):
        request = SimpleNamespace(state=SimpleNamespace())
        assert resolve_tenant(request=request, payload_tenant_id=42) == 42

    def test_authenticated_tenant_wins_and_must_match(self):
        request = SimpleNamespace(state=SimpleNamespace(tenant_id=7))
        assert resolve_tenant(request=request, payload_tenant_id=7) == 7
        with pytest.raises(HTTPException) as excinfo:
            resolve_tenant(request=request, payload_tenant_id=8)
        assert excinfo.value.status_code == 403

    def test_missing_authenticated_tenant_is_401_when_required(self, monkeypatch):
        monkeypatch.setattr(settings, "require_authenticated_tenant", True)
        request = SimpleNamespace(state=SimpleNamespace())
        with pytest.raises(HTTPException) as excinfo:
            resolve_tenant(request=request, payload_tenant_id=1)
        assert excinfo.value.status_code == 401

    def test_job_tenant_ownership_enforced(self):
        request = SimpleNamespace(state=SimpleNamespace(tenant_id=7))
        validate_job_tenant(request, 7)
        with pytest.raises(HTTPException) as excinfo:
            validate_job_tenant(request, 9)
        assert excinfo.value.status_code == 403


class TestPlacementIntoExistingFiles:
    def _repo(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_orders.py").write_text(EXISTING_TEST, encoding="utf-8")
        return str(tmp_path)

    def test_verified_merge_extends_existing_file(self, tmp_path):
        repo = self._repo(tmp_path)
        output = _generated_output()
        decision = TestPlacementDecision(
            generated_path="tests/test_create_order_auth.py",
            action="extend_existing",
            target_existing_path="tests/test_orders.py",
            merged_content=EXISTING_TEST + NEW_TEST_BODY,
            confidence=0.9,
        )
        service = TestPlacementService(
            _StubPlacementAgent(TestPlacementOutput(decisions=[decision]))
        )
        placed, warnings, review_reasons = service.apply(
            repo, output, _profile_with_existing(repo)
        )
        assert placed.files[0].relative_path == "tests/test_orders.py"
        assert "test_create_order_returns_201" in placed.files[0].content
        assert "test_create_order_requires_auth" in placed.files[0].content
        assert not review_reasons
        assert any("merged into existing" in warning for warning in warnings)

    def test_merge_dropping_existing_test_falls_back_to_new_file(self, tmp_path):
        repo = self._repo(tmp_path)
        output = _generated_output()
        lossy_merge = EXISTING_TEST.replace(
            "def test_create_order_rejects_empty_payload(client):",
            "def _renamed(client):",
        ) + NEW_TEST_BODY
        decision = TestPlacementDecision(
            generated_path="tests/test_create_order_auth.py",
            action="extend_existing",
            target_existing_path="tests/test_orders.py",
            merged_content=lossy_merge,
        )
        service = TestPlacementService(
            _StubPlacementAgent(TestPlacementOutput(decisions=[decision]))
        )
        placed, warnings, review_reasons = service.apply(
            repo, output, _profile_with_existing(repo)
        )
        assert placed.files[0].relative_path == "tests/test_create_order_auth.py"
        assert any("was rejected" in reason for reason in review_reasons)

    def test_missing_target_file_falls_back_to_new_file(self, tmp_path):
        repo = self._repo(tmp_path)
        decision = TestPlacementDecision(
            generated_path="tests/test_create_order_auth.py",
            action="extend_existing",
            target_existing_path="tests/test_missing.py",
            merged_content="def test_x():\n    assert True\n",
        )
        service = TestPlacementService(
            _StubPlacementAgent(TestPlacementOutput(decisions=[decision]))
        )
        placed, _, review_reasons = service.apply(
            repo, _generated_output(), _profile_with_existing(repo)
        )
        assert placed.files[0].relative_path == "tests/test_create_order_auth.py"
        assert any("target file does not exist" in reason for reason in review_reasons)

    def test_placement_agent_failure_keeps_new_files(self, tmp_path):
        repo = self._repo(tmp_path)
        service = TestPlacementService(_StubPlacementAgent(error=RuntimeError("llm down")))
        placed, warnings, review_reasons = service.apply(
            repo, _generated_output(), _profile_with_existing(repo)
        )
        assert placed.files[0].relative_path == "tests/test_create_order_auth.py"
        assert any("placement agent failed" in warning.lower() for warning in warnings)
        assert not review_reasons

    def test_no_existing_tests_skips_placement_entirely(self, tmp_path):
        service = TestPlacementService(
            _StubPlacementAgent(error=AssertionError("must not be called"))
        )
        profile = RepoProfile(repo_path=str(tmp_path))
        placed, warnings, review_reasons = service.apply(
            str(tmp_path), _generated_output(), profile
        )
        assert placed.files[0].relative_path == "tests/test_create_order_auth.py"
        assert not warnings and not review_reasons
