from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.base_agent import BaseAgent
from app.coverage.coverage_preservation_service import CoveragePreservationService
from app.governance.generation_budget import (
    BudgetedLLMClient,
    BudgetExceededError,
    GenerationBudget,
)
from app.schemas.exploration import SpecPlacementTurn
from app.schemas.generation_budget import BudgetLimits
from app.schemas.behavioral_test_unit import AnchorFlowContext, BehavioralTestUnit
from app.schemas.code_patch import AppliedPatch, CodePatch, PatchSet, PatchWriteResult
from app.schemas.decision_trace import DecisionTrace
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.generation_request import GenerationRequest
from app.policy.repository_policy_service import RepositoryPolicyService
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.repository_policy import GenerationPolicy, RepositoryPolicy
from app.schemas.spec_placement import SpecPlacementDecision
from app.services.generation_manifest_service import GenerationManifestService
from app.schemas.test_action_decision import (
    TestActionDecision as PlaywrightTestActionDecision,
)
from app.schemas.validation_result import ValidationCheck, ValidationResult
from app.services.review_report_service import ReviewReportService
from app.services.test_value_service import TestValueService
from app.services.traceability_service import TraceabilityService
from app.workspace.workspace_manager import WorkspaceLockedError, WorkspaceManager


EXISTING_SPEC = """import { test, expect } from '@playwright/test';

test.describe('Employee management', () => {
  test('creates an employee', async ({ page }) => {
    await page.goto('/employees');
    await page.click('#create');
    await expect(page.locator('.toast')).toHaveText('Employee created');
  });
});
"""


def _unit_from_spec(path: str, spec: str, title: str) -> BehavioralTestUnit:
    lines = spec.splitlines()
    start = next(index for index, line in enumerate(lines, 1) if title in line)
    end = len(lines) - 1
    return BehavioralTestUnit(
        file_path=path,
        describe_title="Employee management",
        test_title=title,
        start_line=start,
        end_line=end,
        fixtures=["page"],
        page_objects=[],
        source_excerpt="\n".join(lines[start - 1 : end]),
    )


class TestCoveragePreservation:
    def test_snapshot_extracts_behavioral_signals(self) -> None:
        service = CoveragePreservationService()
        unit = _unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")

        [entry] = service.snapshot([unit])

        assert entry.coverage_key == ("e2e/employee.spec.ts", "creates an employee")
        assert entry.navigations == ["/employees"]
        assert entry.interactions == ["click"]
        assert any("toHaveText" in assertion for assertion in entry.assertions)

    def test_appended_test_reports_added_and_preserved(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        appended = EXISTING_SPEC.replace(
            "});\n});",
            "});\n\n  test('shows empty state', async ({ page }) => {\n"
            "    await page.goto('/employees?filter=none');\n"
            "    await expect(page.locator('.empty')).toBeVisible();\n"
            "  });\n});",
        )
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(appended, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content="…")]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is True
        assert [entry.test_title for entry in report.added] == ["shows empty state"]
        assert [entry.test_title for entry in report.preserved] == ["creates an employee"]
        assert report.removed == []
        assert service.review_reasons(report) == []
        assert "Removed: none" in report.summary

    def test_dropped_test_is_reported_as_removed_coverage(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        replaced = EXISTING_SPEC.replace("creates an employee", "updates an employee")
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(replaced, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="replace",
                    start_line=1,
                    end_line=9,
                    content="…",
                )
            ]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is False
        assert [entry.test_title for entry in report.removed] == ["creates an employee"]
        reasons = service.review_reasons(report)
        assert any("Coverage lost" in reason for reason in reasons)

    def test_weakened_assertions_are_reported_as_modified(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        weakened = EXISTING_SPEC.replace(
            "    await expect(page.locator('.toast')).toHaveText('Employee created');\n",
            "",
        )
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(weakened, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="replace",
                    start_line=4,
                    end_line=8,
                    content="…",
                )
            ]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is False
        assert report.removed == []
        [modification] = report.modified
        assert modification.test_title == "creates an employee"
        assert any("toHaveText" in signal for signal in modification.lost_signals)
        reasons = service.review_reasons(report)
        assert any("Coverage weakened" in reason for reason in reasons)

class TestTestValueEvaluator:
    def _existing_unit(self) -> BehavioralTestUnit:
        return _unit_from_spec(
            "e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee"
        )

    def test_duplicate_reimplementation_is_flagged_full_duplicate(self) -> None:
        service = TestValueService()
        duplicate = (
            "test('verifies an employee is created', async ({ page }) => {\n"
            "  await page.goto('/employees');\n"
            "  await page.click('#create');\n"
            "  await expect(page.locator('.toast')).toHaveText('Employee created');\n"
            "});\n"
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts", operation="append", content=duplicate
                )
            ]
        )

        report = service.evaluate(patches, [self._existing_unit()])

        [assessment] = report.assessments
        assert assessment.verdict == "FULL_DUPLICATE"
        assert assessment.closest_existing_test == "creates an employee"
        assert report.requires_approval is True
        assert any("approval required" in reason for reason in service.review_reasons(report))

    def test_unrelated_behavior_is_new_coverage(self) -> None:
        service = TestValueService()
        fresh = (
            "test('exports payroll report', async ({ page }) => {\n"
            "  await page.goto('/payroll/reports');\n"
            "  await page.click('#export');\n"
            "  await expect(page.locator('.download')).toBeVisible();\n"
            "});\n"
        )
        patches = PatchSet(
            patches=[CodePatch(path="e2e/payroll.spec.ts", operation="create", content=fresh)]
        )

        report = service.evaluate(patches, [self._existing_unit()])

        [assessment] = report.assessments
        assert assessment.verdict == "NEW_COVERAGE"
        assert report.requires_approval is False
        assert service.review_reasons(report) == []

    def test_assertionless_test_is_low_value(self) -> None:
        service = TestValueService()
        hollow = (
            "test('opens the page', async ({ page }) => {\n"
            "  await page.goto('/employees');\n"
            "});\n"
        )
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content=hollow)]
        )

        report = service.evaluate(patches, [self._existing_unit()])

        [assessment] = report.assessments
        assert assessment.verdict == "LOW_VALUE"
        assert any("low value" in reason for reason in service.review_reasons(report))

    def test_reemitted_existing_test_is_not_reevaluated(self) -> None:
        service = TestValueService()
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="replace",
                    start_line=4,
                    end_line=8,
                    content=(
                        "test('creates an employee', async ({ page }) => {\n"
                        "  await page.goto('/employees');\n"
                        "  await expect(page.locator('.toast')).toBeVisible();\n"
                        "});\n"
                    ),
                )
            ]
        )

        report = service.evaluate(patches, [self._existing_unit()])

        assert report.assessments == []
        assert "No newly generated tests" in report.summary


class TestRequirementTraceability:
    def _request(self, steps: list[str]) -> GenerationRequest:
        return GenerationRequest(
            job_id="job-1",
            repo_path="/tmp/repo",
            test_case_name="Employee empty state",
            steps=steps,
        )

    def test_requirements_map_to_generated_and_existing_code(self) -> None:
        service = TraceabilityService()
        intent = FunctionalIntent(
            capability="Employee empty state",
            assertions=["Verify empty state banner is visible"],
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="append",
                    content=(
                        "test('shows empty state banner', async ({ page }) => {\n"
                        "  await page.goto('/employees?filter=none');\n"
                        "  await expect(page.locator('.empty-state-banner')).toBeVisible();\n"
                        "});\n"
                    ),
                )
            ]
        )
        existing = [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]

        matrix = service.build(
            self._request(["Create an employee", "Verify empty state banner visible"]),
            intent,
            patches,
            existing,
        )

        assert matrix.complete is True
        assert matrix.missing == 0
        by_requirement = {trace.requirement: trace for trace in matrix.requirements}
        assert by_requirement["Create an employee"].source == "existing_flow"
        assert "creates an employee" in by_requirement["Create an employee"].covered_by
        assert by_requirement["Verify empty state banner visible"].source == "generated"
        assert (
            by_requirement["Verify empty state banner visible"].covered_by
            == "e2e/employee.spec.ts"
        )
        assert service.review_reasons(matrix) == []

    def test_unimplemented_requirement_is_reported_missing(self) -> None:
        service = TraceabilityService()
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="append",
                    content="test('noop', async ({ page }) => {});\n",
                )
            ]
        )

        matrix = service.build(
            self._request(["Export quarterly payroll summary as PDF"]),
            FunctionalIntent(),
            patches,
            [],
        )

        assert matrix.complete is False
        assert matrix.missing == 1
        [trace] = matrix.requirements
        assert trace.status == "missing"
        assert trace.covered_by is None
        reasons = service.review_reasons(matrix)
        assert reasons == [
            "Requirement not traceable to any code: "
            "'Export quarterly payroll summary as PDF'."
        ]


class TestReviewReport:
    def test_report_condenses_generation_into_reviewable_sections(self) -> None:
        service = ReviewReportService()
        request = GenerationRequest(
            job_id="job-1",
            repo_path="/tmp/repo",
            test_case_name="Employee empty state",
        )
        action = PlaywrightTestActionDecision(
            action="append_new_test",
            confidence=0.8,
            decision_trace=DecisionTrace(
                decision="append_new_test",
                confidence=0.8,
                justification="Target spec owns the employee flow; appending is additive.",
                evidence=["employee.spec.ts owns the flow"],
            ),
        )
        anchor = AnchorFlowContext(
            file_path="e2e/employee.spec.ts",
            anchor_test_title="creates an employee",
            page_objects=["EmployeePage"],
            fixtures=["page"],
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="append",
                    reason="Cover the empty state behavior",
                    content=(
                        "test('shows empty state', async ({ page }) => {\n"
                        "  const employeePage = new EmployeePage(page);\n"
                        "  await employeePage.gotoList();\n"
                        "  await expect(page.locator('.empty')).toBeVisible();\n"
                        "});\n"
                    ),
                ),
                CodePatch(
                    path="pages/employee.page.ts",
                    operation="replace",
                    start_line=10,
                    end_line=12,
                    content="  async filterByNone(): Promise<void> {\n    await this.filter.click();\n  }\n",
                ),
            ]
        )
        patch_result = PatchWriteResult(
            applied=[
                AppliedPatch(path="e2e/employee.spec.ts", operation="append", diff="…"),
                AppliedPatch(path="pages/employee.page.ts", operation="replace", diff="…"),
            ]
        )
        validation = ValidationResult(
            passed=True,
            checks=[ValidationCheck(name="tsc", passed=True)],
        )

        report = service.build(
            request,
            action=action,
            anchor_flow_context=anchor,
            patches=patches,
            patch_result=patch_result,
            validation=validation,
            review_reasons=["Spec placement confidence 0.40 is below the review threshold 0.50."],
        )

        assert "2 patch(es) planned, 2 applied" in report.summary
        assert [change.path for change in report.files_changed] == [
            "e2e/employee.spec.ts",
            "pages/employee.page.ts",
        ]
        assert any("creates an employee" in flow for flow in report.flows_reused)
        assert report.action == "append_new_test"
        assert "appending is additive" in report.action_rationale
        assert "pages/employee.page.ts: filterByNone()" in report.methods_created
        assert "employeePage.gotoList()" in report.methods_reused
        assert any("toBeVisible" in assertion for assertion in report.assertions_added)
        assert report.validation_summary == "Validation passed (1 check(s))."
        assert len(report.remaining_risks) == 1
        for heading in (
            "# Generation Review Report",
            "## Files Changed",
            "## Flow Reused",
            "## Why append_new_test",
            "## Methods Created",
            "## Locators Reused",
            "## Assertions Added",
            "## Validation",
            "## Remaining Risks",
        ):
            assert heading in report.markdown

    def test_report_surfaces_failed_validation_and_empty_sections(self) -> None:
        service = ReviewReportService()
        request = GenerationRequest(
            job_id="job-2", repo_path="/tmp/repo", test_case_name="Broken run"
        )
        validation = ValidationResult(
            passed=False,
            checks=[ValidationCheck(name="playwright_dry_run", passed=False)],
            repair_attempted=True,
        )

        report = service.build(request, validation=validation)

        assert "Validation FAILED" in report.validation_summary
        assert "playwright_dry_run" in report.validation_summary
        assert "repair attempted" in report.validation_summary
        assert "- None identified" in report.markdown


class TestRepositoryPolicy:
    def test_defaults_apply_when_no_policy_file_exists(self, tmp_path: Path) -> None:
        service = RepositoryPolicyService()

        policy = service.load(str(tmp_path))

        assert policy.source == "defaults"
        assert policy.generation.allow_before_each_updates is True
        assert policy.generation.assertion_location == "any"
        assert policy.generation.rollback_failed_patch is True

    def test_policy_file_is_loaded_without_yaml_dependency(self, tmp_path: Path) -> None:
        service = RepositoryPolicyService()
        policy_dir = tmp_path / ".movr"
        policy_dir.mkdir()
        (policy_dir / "test-agent-policy.yaml").write_text(
            "# repository generation rules\n"
            "generation:\n"
            "  allow_before_each_updates: false\n"
            "  assertion_location: spec\n"
            "  locator_owner: page_object\n"
            "  require_describe: true\n"
            "  rollback_failed_patch: false\n",
            encoding="utf-8",
        )

        policy = service.load(str(tmp_path))

        assert policy.source == ".movr/test-agent-policy.yaml"
        assert policy.generation.allow_before_each_updates is False
        assert policy.generation.assertion_location == "spec"
        assert policy.generation.locator_owner == "page_object"
        assert policy.generation.require_describe is True
        assert policy.generation.rollback_failed_patch is False

    def test_policy_checks_flag_violations(self) -> None:
        service = RepositoryPolicyService()
        policy = RepositoryPolicy(
            generation=GenerationPolicy(
                allow_before_each_updates=False,
                assertion_location="spec",
                locator_owner="page_object",
                require_describe=True,
            )
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="append",
                    content=(
                        "test.beforeEach(async ({ page }) => { await page.goto('/'); });\n"
                        "test('x', async ({ page }) => {\n"
                        "  await expect(page.locator('.empty')).toBeVisible();\n"
                        "});\n"
                    ),
                ),
                CodePatch(
                    path="pages/employee.page.ts",
                    operation="replace",
                    start_line=1,
                    end_line=2,
                    content="async assertVisible() { await expect(this.row).toBeVisible(); }\n",
                ),
                CodePatch(
                    path="e2e/new-flow.spec.ts",
                    operation="create",
                    content="import { test, expect } from '@playwright/test';\ntest('y', async () => {});\n",
                ),
            ]
        )

        checks = {check.name: check for check in service.checks(patches, policy)}

        assert checks["policy_before_each"].passed is False
        assert "beforeEach" in checks["policy_before_each"].output
        assert checks["policy_assertion_location"].passed is False
        assert "pages/employee.page.ts" in checks["policy_assertion_location"].output
        assert checks["policy_locator_owner"].passed is False
        assert "e2e/employee.spec.ts" in checks["policy_locator_owner"].output
        assert checks["policy_require_describe"].passed is False
        assert "e2e/new-flow.spec.ts" in checks["policy_require_describe"].output

    def test_permissive_policy_passes_all_checks(self) -> None:
        service = RepositoryPolicyService()
        policy = RepositoryPolicy()
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="append",
                    content="test('x', async ({ page }) => { await expect(page.locator('.a')).toBeVisible(); });\n",
                )
            ]
        )

        checks = service.checks(patches, policy)

        assert all(check.passed for check in checks)

    def test_full_duplicates_allowed_by_policy_are_not_flagged(self) -> None:
        value_service = TestValueService()
        duplicate = (
            "test('verifies an employee is created', async ({ page }) => {\n"
            "  await page.goto('/employees');\n"
            "  await page.click('#create');\n"
            "  await expect(page.locator('.toast')).toHaveText('Employee created');\n"
            "});\n"
        )
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content=duplicate)]
        )
        existing = [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]

        report = value_service.evaluate(patches, existing)

        assert report.requires_approval is True
        assert value_service.review_reasons(report, allow_full_duplicates=True) == []
        assert value_service.review_reasons(report) != []


class TestGenerationManifest:
    def _request(self) -> GenerationRequest:
        return GenerationRequest(
            job_id="job-1",
            repo_path="/tmp/repo",
            branch="main",
            test_case_name="Employee empty state",
            steps=["Open employees", "Verify empty state"],
        )

    def _inventory(self) -> RepositoryInventory:
        return RepositoryInventory(
            repo_path="/tmp/repo",
            repo_head="abc123",
            file_hashes={"e2e/employee.spec.ts": "hash-1", "pages/employee.page.ts": "hash-2"},
        )

    def test_manifest_freezes_run_inputs_and_decisions(self) -> None:
        service = GenerationManifestService()
        placement = SpecPlacementDecision(
            target_spec_file="e2e/employee.spec.ts", confidence=0.9
        )
        action = PlaywrightTestActionDecision(action="append_new_test", confidence=0.8)
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content="test…")]
        )

        manifest = service.build(
            self._request(),
            inventory=self._inventory(),
            policy=RepositoryPolicy(),
            model_provider="anthropic",
            decisions=[
                ("spec_placement", placement),
                ("test_action", action),
                ("flow_merge", None),
            ],
            patches=patches,
        )

        assert manifest.repo_head == "abc123"
        assert manifest.repository_snapshot_digest != ""
        assert manifest.model_provider == "anthropic"
        assert manifest.prompt_versions  # every prompt module fingerprinted
        assert all(len(digest) == 12 for digest in manifest.prompt_versions.values())
        assert manifest.settings_snapshot["max_repair_attempts"] == "2"
        assert manifest.policy_snapshot["rollback_failed_patch"] == "True"
        assert [decision.stage for decision in manifest.decisions] == [
            "spec_placement",
            "test_action",
        ]
        assert manifest.decisions[0].decision == "e2e/employee.spec.ts"
        assert manifest.decisions[1].decision == "append_new_test"
        [patch_record] = manifest.patches
        assert patch_record.content_digest != ""
        assert manifest.generation_fingerprint != ""

    def test_same_inputs_produce_same_fingerprint_and_changed_inputs_do_not(self) -> None:
        service = GenerationManifestService()

        first = service.build(self._request(), inventory=self._inventory(), model_provider="anthropic")
        second = service.build(self._request(), inventory=self._inventory(), model_provider="anthropic")
        changed_repo = service.build(
            self._request(),
            inventory=RepositoryInventory(
                repo_path="/tmp/repo",
                repo_head="def456",
                file_hashes={"e2e/employee.spec.ts": "hash-CHANGED"},
            ),
            model_provider="anthropic",
        )

        assert first.generation_fingerprint == second.generation_fingerprint
        assert first.generation_fingerprint != changed_repo.generation_fingerprint


class TestGenerationBudget:
    def test_llm_calls_beyond_limit_escalate(self) -> None:
        budget = GenerationBudget(limits=BudgetLimits(max_llm_calls=2))

        budget.charge_llm_call(prompt_chars=100)
        budget.charge_llm_call(prompt_chars=100)
        with pytest.raises(BudgetExceededError) as excinfo:
            budget.charge_llm_call(prompt_chars=100)

        assert "llm_calls used 3 of 2" in str(excinfo.value)
        assert excinfo.value.report.escalated is True
        assert excinfo.value.report.usage.llm_calls == 3

    def test_budgeted_client_charges_every_model_and_tool_call(self) -> None:
        class FakeClient:
            def complete(self, prompt: str) -> str:
                return "ok"

            def complete_structured(self, prompt: str, response_model: type) -> object:
                return object()

        budget = GenerationBudget(limits=BudgetLimits())
        client = BudgetedLLMClient(FakeClient(), budget)

        client.complete("prompt text")
        client.complete_structured(prompt="structured prompt", response_model=object)
        client.charge_tool_call()
        client.charge_repository_read()
        report = budget.report()

        assert report.usage.llm_calls == 2
        assert report.usage.prompt_chars == len("prompt text") + len("structured prompt")
        assert report.usage.completion_chars == len("ok")
        assert report.usage.tool_calls == 1
        assert report.usage.repository_reads == 1
        assert report.escalated is False
        assert report.usage.elapsed_seconds >= 0.0

    def test_exploration_loop_charges_repository_reads(self, tmp_path: Path) -> None:
        budget = GenerationBudget(limits=BudgetLimits(max_repository_reads=1))

        class ScriptedClient:
            def complete_structured(self, prompt: str, response_model: type):
                return response_model.model_validate(
                    {
                        "reasoning": "need evidence",
                        "requests": [
                            {"kind": "read_file", "target": "a.ts", "reason": "check"},
                            {"kind": "read_file", "target": "b.ts", "reason": "check"},
                        ],
                        "output": None,
                    }
                )

        agent = BaseAgent(llm_client=BudgetedLLMClient(ScriptedClient(), budget))

        with pytest.raises(BudgetExceededError) as excinfo:
            agent.complete_with_exploration(
                "explore", SpecPlacementTurn, repo_path=str(tmp_path), max_turns=3
            )

        assert "repository_reads" in str(excinfo.value)

    def test_time_budget_escalates(self) -> None:
        budget = GenerationBudget(
            limits=BudgetLimits(max_generation_seconds=0.0)
        )

        with pytest.raises(BudgetExceededError) as excinfo:
            budget.charge_tool_call()

        assert "elapsed" in str(excinfo.value)


class TestWorkspaceIsolation:
    def test_second_job_on_same_repo_is_locked_out(self, tmp_path: Path) -> None:
        manager = WorkspaceManager(workspace_root=str(tmp_path / "ws"))
        repo = tmp_path / "repo"
        repo.mkdir()

        first = manager.acquire("job-a", str(repo))
        with pytest.raises(WorkspaceLockedError) as excinfo:
            manager.acquire("job-b", str(repo))
        assert "job-a" in str(excinfo.value)

        manager.release(first)
        second = manager.acquire("job-b", str(repo))
        assert second.job_id == "job-b"
        manager.release(second)

    def test_different_repos_do_not_contend(self, tmp_path: Path) -> None:
        manager = WorkspaceManager(workspace_root=str(tmp_path / "ws"))
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        repo_a.mkdir()
        repo_b.mkdir()

        first = manager.acquire("job-a", str(repo_a))
        second = manager.acquire("job-b", str(repo_b))

        assert first.root != second.root
        manager.release(first)
        manager.release(second)

    def test_journals_and_snapshot_record_job_activity(self, tmp_path: Path) -> None:
        manager = WorkspaceManager(workspace_root=str(tmp_path / "ws"))
        repo = tmp_path / "repo"
        (repo / "e2e").mkdir(parents=True)
        spec = repo / "e2e" / "employee.spec.ts"
        spec.write_text("original content\n", encoding="utf-8")

        workspace = manager.acquire("job-a", str(repo))
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content="new\n")]
        )
        manager.snapshot_targets(workspace, patches)
        write_result = PatchWriteResult(
            applied=[AppliedPatch(path="e2e/employee.spec.ts", operation="append", diff="…")]
        )
        manager.record_patches(workspace, write_result)
        manager.record_rollback(workspace, write_result)

        snapshot = workspace.snapshot_dir / "e2e" / "employee.spec.ts"
        assert snapshot.read_text(encoding="utf-8") == "original content\n"
        patch_entries = [
            json.loads(line)
            for line in workspace.patch_journal.read_text(encoding="utf-8").splitlines()
        ]
        assert patch_entries[0]["path"] == "e2e/employee.spec.ts"
        assert patch_entries[0]["job_id"] == "job-a"
        rollback_entries = workspace.rollback_journal.read_text(encoding="utf-8").splitlines()
        assert len(rollback_entries) == 1
        manager.release(workspace)

    def test_stale_lock_is_reclaimed(self, tmp_path: Path) -> None:
        manager = WorkspaceManager(workspace_root=str(tmp_path / "ws"))
        manager.stale_lock_seconds = 0.0
        repo = tmp_path / "repo"
        repo.mkdir()

        manager.acquire("job-dead", str(repo))
        reclaimed = manager.acquire("job-live", str(repo))

        assert reclaimed.job_id == "job-live"
        manager.release(reclaimed)
