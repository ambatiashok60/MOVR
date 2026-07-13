from __future__ import annotations

from worktop.test_agent.app.llm.default_llm_client import DefaultLLMClientAdapter
from worktop.test_agent.app.prompts.functional_intent_prompt import (
    build_functional_intent_prompt,
)
from worktop.test_agent.app.prompts.code_generation_prompt import build_code_generation_prompt
from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit, ExistingTestContext
from worktop.test_agent.app.schemas.code_patch import AppliedPatch, CodePatch, PatchSet, PatchWriteResult
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision as PlaywrightTestActionDecision
from worktop.test_agent.app.schemas.validation_result import ValidationCheck, ValidationResult
from worktop.test_agent.app.services.behavioral_inventory_service import BehavioralInventoryService
from worktop.test_agent.app.services.generation_orchestrator import GenerationOrchestrator
from worktop.test_agent.app.tools.playwright_parser_tool import PlaywrightParserTool


class RepairingClient(DefaultLLMClientAdapter):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        return self.responses.pop(0)


def test_functional_intent_accepts_rich_transition_and_assertion_objects() -> None:
    intent = FunctionalIntent.model_validate(
        {
            "capability": "Plan design navigation",
            "actor": "Designer",
            "journey": [{"step": "Open landing page"}],
            "state_transitions": [
                {
                    "from_state": "Landing Page",
                    "to_state": "Plan Design Page",
                    "trigger": "Click on Plan Design tile",
                    "expected_outcome": "URL matches expected route",
                }
            ],
            "assertions": [
                {
                    "type": "navigation",
                    "description": "Verify current URL matches the expected plan design route",
                }
            ],
        }
    )

    assert intent.journey == ["Open landing page"]
    assert intent.state_transitions == [
        "Landing Page -> Plan Design Page; trigger: Click on Plan Design tile; "
        "expected outcome: URL matches expected route"
    ]
    assert intent.assertions == [
        "navigation: Verify current URL matches the expected plan design route"
    ]


def test_functional_intent_prompt_includes_exact_schema_contract() -> None:
    request = GenerationRequest(
        job_id="job-1",
        tenant_id="tenant-1",
        repo_path="/tmp/repo",
        test_case_name="Plan design navigation",
    )

    prompt = build_functional_intent_prompt(request)

    assert "JSON schema:" in prompt
    assert "FunctionalIntent" in prompt
    assert '"state_transitions"' in prompt
    assert "For arrays whose item type is string" in prompt
    assert "Valid response example:" in prompt
    assert "Invalid response example:" in prompt
    assert "Do not invent extra keys" in prompt
    assert "All generated code must be inside a schema field" in prompt


def test_structured_parser_extracts_json_from_markdown_fence() -> None:
    adapter = object.__new__(DefaultLLMClientAdapter)
    response = """
Here is the JSON:

```json
{
  "capability": "Plan design navigation",
  "actor": "Designer",
  "journey": ["Open landing page"],
  "state_transitions": [],
  "assertions": []
}
```
"""

    intent = adapter._parse_structured_response(response, FunctionalIntent)

    assert intent.capability == "Plan design navigation"
    assert intent.journey == ["Open landing page"]


def test_complete_structured_repairs_invalid_first_response() -> None:
    client = RepairingClient(
        [
            '{"capability": {"name": "bad shape"}, "state_transitions": [], "assertions": []}',
            '{"capability": "Plan design navigation", "actor": "", "journey": [], '
            '"state_transitions": [], "assertions": []}',
        ]
    )

    intent = client.complete_structured("extract intent", FunctionalIntent)

    assert intent.capability == "Plan design navigation"
    assert client.responses == []


def test_test_action_decision_rejects_unknown_action_value() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlaywrightTestActionDecision.model_validate(
            {"action": "rewrite_everything", "confidence": 0.9}
        )


def test_decision_confidence_is_bounded_to_unit_interval() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlaywrightTestActionDecision.model_validate(
            {"action": "append_new_test", "confidence": 1.5}
        )
    with pytest.raises(ValidationError):
        SpecPlacementDecision.model_validate(
            {"target_spec_file": "tests/x.spec.ts", "confidence": -0.2}
        )


def _make_unit(title: str, line: int) -> BehavioralTestUnit:
    return BehavioralTestUnit(
        file_path="tests/plans.spec.ts",
        test_title=title,
        start_line=line,
        end_line=line + 5,
        source_excerpt=f"test('{title}', async ({{ page }}) => {{}});",
    )


def test_candidate_ranking_passes_through_without_intent_or_llm() -> None:
    from worktop.test_agent.app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent

    agent = CandidateTestRankingAgent()
    candidates = [_make_unit("a", 1), _make_unit("b", 10)]
    assert agent.rank(candidates, intent=None) == candidates


def test_candidate_ranking_reorders_from_model_ranking() -> None:
    from worktop.test_agent.app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent
    from worktop.test_agent.app.schemas.candidate_ranking import CandidateRanking, RankedCandidateRef

    agent = CandidateTestRankingAgent()
    first = _make_unit("first", 1)
    second = _make_unit("second", 10)
    ranking = CandidateRanking(
        ranked=[
            RankedCandidateRef(file_path="tests/plans.spec.ts", test_title="second", start_line=10),
            RankedCandidateRef(file_path="tests/plans.spec.ts", test_title="first", start_line=1),
        ]
    )
    ordered = agent._apply_ranking([first, second], ranking)
    assert [unit.test_title for unit in ordered] == ["second", "first"]


def test_candidate_ranking_keeps_unreferenced_candidates_at_end() -> None:
    from worktop.test_agent.app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent
    from worktop.test_agent.app.schemas.candidate_ranking import CandidateRanking, RankedCandidateRef

    agent = CandidateTestRankingAgent()
    a = _make_unit("a", 1)
    b = _make_unit("b", 10)
    c = _make_unit("c", 20)
    ranking = CandidateRanking(
        ranked=[RankedCandidateRef(file_path="tests/plans.spec.ts", test_title="c", start_line=20)]
    )
    ordered = agent._apply_ranking([a, b, c], ranking)
    assert [unit.test_title for unit in ordered] == ["c", "a", "b"]


def test_candidate_ranking_uses_llm_ranking_end_to_end() -> None:
    from worktop.test_agent.app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent

    client = RepairingClient(
        [
            '{"ranked": [{"file_path": "tests/plans.spec.ts", "test_title": "second", '
            '"start_line": 10, "relevance": 0.9, "reason": "same route"}, '
            '{"file_path": "tests/plans.spec.ts", "test_title": "first", '
            '"start_line": 1, "relevance": 0.2, "reason": "unrelated"}]}'
        ]
    )
    agent = CandidateTestRankingAgent(llm_client=client)
    ordered = agent.rank(
        [_make_unit("first", 1), _make_unit("second", 10)],
        intent=FunctionalIntent(capability="open plan design"),
    )
    assert [unit.test_title for unit in ordered] == ["second", "first"]


def test_ownership_prompt_includes_reuse_vs_create_standards() -> None:
    from worktop.test_agent.app.prompts.ownership_resolution_prompt import build_ownership_resolution_prompt
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory

    prompt = build_ownership_resolution_prompt(
        RepositoryInventory(repo_path="/tmp/repo", repo_head="abc")
    )
    assert "Reuse an existing owner (set create_new=false)" in prompt
    assert "Create a new owner (set create_new=true)" in prompt
    assert "decision_trace" in prompt


def test_ownership_fallback_reuses_existing_owner_with_trace() -> None:
    from worktop.test_agent.app.agents.ownership_resolution_agent import OwnershipResolutionAgent
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory

    agent = OwnershipResolutionAgent()
    inventory = RepositoryInventory(
        repo_path="/tmp/repo",
        repo_head="abc",
        page_objects=["pages/PlanPage.ts"],
    )
    resolution = agent._fallback_resolution(inventory)
    assert resolution.owner_path == "pages/PlanPage.ts"
    assert resolution.owner_kind == "page_object"
    assert resolution.create_new is False
    assert resolution.decision_trace.decision == "reuse_existing_page_object"


def test_low_ownership_confidence_is_flagged_for_review() -> None:
    from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution

    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_low_ownership_confidence(
        OwnershipResolution(
            owner_path="pages/PlanPage.ts",
            owner_kind="page_object",
            confidence=0.2,
        ),
        reasons,
    )
    assert len(reasons) == 1
    assert "Ownership resolution confidence" in reasons[0]


def test_low_ownership_confidence_flag_ignores_missing_resolution() -> None:
    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_low_ownership_confidence(None, reasons)
    assert reasons == []


def _anchor_unit(title: str, line: int, page_objects=None, fixtures=None) -> BehavioralTestUnit:
    return BehavioralTestUnit(
        file_path="tests/plans.spec.ts",
        test_title=title,
        start_line=line,
        end_line=line + 5,
        page_objects=page_objects or [],
        fixtures=fixtures or ["page"],
        source_excerpt=f"test('{title}', async ({{ page }}) => {{}});",
    )


def test_anchor_flow_context_reads_only_placement_selected_file(tmp_path) -> None:
    target = tmp_path / "tests" / "plans.spec.ts"
    target.parent.mkdir()
    target.write_text(
        """import { test } from '@playwright/test';
test.describe('plans', () => {
  test('first', async ({ page }) => { await page.goto('/plans'); });
  test('second', async ({ page }) => { await page.goto('/plans/2'); });
});
""",
        encoding="utf-8",
    )
    orchestrator = GenerationOrchestrator()
    anchor = orchestrator._resolve_anchor_flow_context(
        placement=SpecPlacementDecision(target_spec_file="tests/plans.spec.ts", create_new=False),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        candidates=[
            _anchor_unit("rich", 10, page_objects=["LoginPage", "PlanPage"], fixtures=["page", "storageState"]),
        ],
        repo_path=str(tmp_path),
    )
    assert anchor is not None
    assert anchor.anchor_test_title == "first"
    assert "placement-selected suite" in anchor.rationale


def test_behavior_after_placement_is_scoped_to_selected_spec() -> None:
    orchestrator = GenerationOrchestrator()
    selected = _anchor_unit("selected", 1)
    unrelated = selected.model_copy(
        update={"file_path": "tests/unrelated.spec.ts", "test_title": "unrelated"}
    )

    scoped = orchestrator._behavior_for_placement(
        SpecPlacementDecision(
            target_spec_file="./tests/plans.spec.ts", create_new=False
        ),
        [unrelated, selected],
    )

    assert scoped == [selected]


def test_existing_context_does_not_fall_back_to_another_test() -> None:
    orchestrator = GenerationOrchestrator()
    context = orchestrator._resolve_existing_test_context(
        SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts", create_new=False
        ),
        PlaywrightTestActionDecision(
            action="extend_existing_test", target_test_title="missing title"
        ),
        [_anchor_unit("different test", 1)],
    )

    assert context is None


def test_extend_decision_carries_stable_selected_test_identity() -> None:
    from worktop.test_agent.app.services.test_action_service import TestActionService

    candidate = _anchor_unit("Opens   Plan", 12)
    decision = TestActionService()._bind_selected_test_identity(
        PlaywrightTestActionDecision(
            action="extend_existing_test", target_test_title=" opens plan "
        ),
        [candidate],
    )

    assert decision.target_test_title == candidate.test_title
    assert decision.target_file_path == candidate.file_path
    assert decision.target_start_line == candidate.start_line


def test_anchor_flow_context_uses_agent_ranking_within_target_file(tmp_path) -> None:
    target = tmp_path / "tests" / "plans.spec.ts"
    target.parent.mkdir()
    target.write_text(
        """import { test } from '@playwright/test';
test.describe('plans', () => {
  test('opens a plan', async ({ page }) => { await page.goto('/plans'); });
  test('saves a plan', async ({ page }) => { await page.goto('/plans/new'); });
});
""",
        encoding="utf-8",
    )

    class RankingAgent:
        def rank(self, candidates, intent):
            assert {candidate.test_title for candidate in candidates} == {
                "opens a plan",
                "saves a plan",
            }
            return [candidates[1], candidates[0]]

    anchor = GenerationOrchestrator()._resolve_anchor_flow_context(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts", create_new=False
        ),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        candidates=[_anchor_unit("unrelated repository test", 1)],
        repo_path=str(tmp_path),
        intent=object(),
        ranking_agent=RankingAgent(),
    )

    assert anchor is not None
    assert anchor.anchor_test_title == "saves a plan"
    assert "agent-ranked" in anchor.rationale


def test_anchor_flow_context_skipped_for_non_append() -> None:
    orchestrator = GenerationOrchestrator()
    anchor = orchestrator._resolve_anchor_flow_context(
        placement=SpecPlacementDecision(target_spec_file="tests/plans.spec.ts", create_new=False),
        action=PlaywrightTestActionDecision(action="extend_existing_test"),
        candidates=[_anchor_unit("rich", 10, page_objects=["LoginPage"])],
    )
    assert anchor is None


def test_anchor_flow_context_none_when_target_suite_has_no_tests(tmp_path) -> None:
    target = tmp_path / "tests" / "other.spec.ts"
    target.parent.mkdir()
    target.write_text("import { test } from '@playwright/test';\n", encoding="utf-8")
    orchestrator = GenerationOrchestrator()
    anchor = orchestrator._resolve_anchor_flow_context(
        placement=SpecPlacementDecision(target_spec_file="tests/other.spec.ts", create_new=False),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        candidates=[_anchor_unit("rich", 10, page_objects=["LoginPage"])],
        repo_path=str(tmp_path),
    )
    assert anchor is None


def test_code_generation_prompt_includes_anchor_flow_and_append_rules() -> None:
    from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext

    prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(target_spec_file="tests/plans.spec.ts", create_new=False),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        anchor_flow_context=AnchorFlowContext(
            file_path="tests/plans.spec.ts",
            anchor_test_title="logs in and opens plan",
            page_objects=["LoginPage"],
            fixtures=["storageState"],
        ),
    )
    assert "Anchor flow context:" in prompt
    assert "copy that sibling test's setup" in prompt
    assert "never edit or replace the original anchor test" in prompt
    assert "LoginPage" in prompt


def test_locator_prompt_targets_only_new_append_actions() -> None:
    from worktop.test_agent.app.prompts.locator_reasoning_prompt import build_locator_reasoning_prompt
    from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext
    from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence

    prompt = build_locator_reasoning_prompt(
        SourceIntelligence(),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        anchor=AnchorFlowContext(
            file_path="tests/plans.spec.ts",
            describe_title="plans",
            anchor_test_title="opens plan",
            behavior_summary="Open an existing plan.",
            source_excerpt="await planPage.open();",
        ),
    )

    assert "return decisions only for new interactions" in prompt
    assert "await planPage.open();" in prompt
    assert "Preserve locators and page-object calls" in prompt


def test_append_reuse_check_fails_when_no_overlap() -> None:
    from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext

    orchestrator = GenerationOrchestrator()
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        anchor_test_title="logs in and opens plan",
        page_objects=["LoginPage"],
        fixtures=["storageState"],
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                content=(
                    "test('new', async ({ page }) => {\n"
                    "// Anchor flow: logs in and opens plan\n"
                    "await page.goto('/');\n"
                    "// End anchor flow; new scenario steps begin below.\n"
                    "});"
                ),
            )
        ]
    )
    check = orchestrator._append_reuse_check(patches, anchor)
    assert check.passed is True
    assert "Non-blocking anchor reuse warning" in check.output


def test_append_reuse_check_passes_when_anchor_page_object_reused() -> None:
    from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext

    orchestrator = GenerationOrchestrator()
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        anchor_test_title="logs in and opens plan",
        page_objects=["LoginPage"],
        fixtures=["storageState"],
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                content=(
                    "test('new', async ({ page }) => {\n"
                    "// Anchor flow: logs in and opens plan\n"
                    "const lp = new LoginPage(page);\n"
                    "// End anchor flow; new scenario steps begin below.\n"
                    "});"
                ),
            )
        ]
    )
    check = orchestrator._append_reuse_check(patches, anchor)
    assert check.passed is True


def test_append_reuse_check_noop_without_reusable_signals() -> None:
    from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext

    orchestrator = GenerationOrchestrator()
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        anchor_test_title="bare",
        page_objects=[],
        fixtures=["page"],
    )
    check = orchestrator._append_reuse_check(PatchSet(patches=[]), anchor)
    assert check.passed is True


def test_flow_merge_prompt_grounds_in_existing_test_source() -> None:
    from worktop.test_agent.app.prompts.flow_merge_prompt import build_flow_merge_prompt

    prompt = build_flow_merge_prompt(
        FunctionalIntent(capability="open plan design"),
        ExistingTestContext(
            file_path="tests/plans.spec.ts",
            test_title="opens plan design",
            start_line=10,
            end_line=18,
            source_excerpt="test('opens plan design', async ({ page }) => {});",
        ),
    )
    assert "Existing test context (source of the proven flow)" in prompt
    assert "Derive the stable_region and preserved_steps from the Existing test context" in prompt


def test_flow_merge_plan_has_confidence_and_trace() -> None:
    from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan

    plan = FlowMergePlan(preserved_steps=["await page.goto('/')"], confidence=0.4)
    assert plan.confidence == 0.4
    assert plan.decision_trace.decision == "undecided"


def test_low_flow_merge_confidence_flagged() -> None:
    from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan

    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_low_flow_merge_confidence(FlowMergePlan(confidence=0.2), reasons)
    assert reasons and "Flow merge confidence" in reasons[0]


def test_dropped_preserved_step_is_flagged() -> None:
    from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan

    orchestrator = GenerationOrchestrator()
    existing = ExistingTestContext(
        file_path="tests/plans.spec.ts",
        test_title="opens plan design",
        start_line=10,
        end_line=18,
        source_excerpt=(
            "test('opens plan design', async ({ page }) => {\n"
            "  await page.goto('/dashboard');\n"
            "  await expect(page).toHaveURL(/dashboard/);\n"
            "});"
        ),
    )
    flow_plan = FlowMergePlan(preserved_steps=["await page.goto('/dashboard');"])
    # Replacement drops the proven goto step.
    findings = orchestrator._dropped_preserved_steps(
        existing,
        flow_plan,
        "test('opens plan design', async ({ page }) => { await expect(page).toHaveURL(/x/); });",
    )
    assert findings and "goto('/dashboard')" in findings[0]


def test_preserved_step_not_in_source_is_not_enforced() -> None:
    from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan

    orchestrator = GenerationOrchestrator()
    existing = ExistingTestContext(
        file_path="tests/plans.spec.ts",
        test_title="opens plan design",
        start_line=10,
        end_line=18,
        source_excerpt="test('opens plan design', async ({ page }) => {});",
    )
    # Paraphrased step that is not a literal substring of the source: must not fire.
    flow_plan = FlowMergePlan(preserved_steps=["navigate to the dashboard"])
    findings = orchestrator._dropped_preserved_steps(existing, flow_plan, "unrelated content")
    assert findings == []


def test_code_generation_prompt_includes_locator_decisions_and_rules() -> None:
    from worktop.test_agent.app.schemas.locator_decision import LocatorDecision

    prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(target_spec_file="tests/plans.spec.ts"),
        action=PlaywrightTestActionDecision(action="append_new_test"),
        locator_decisions=[
            LocatorDecision(
                locator="page.getByRole('button', { name: 'Plan Design' })",
                source_evidence=["plan-tile.component.html"],
                confidence=0.9,
            )
        ],
    )
    assert "Locator decisions (evidence-grounded" in prompt
    assert "getByRole('button', { name: 'Plan Design' })" in prompt
    assert "use exactly those locators" in prompt
    assert "does not already exist in the repository or in a patch" in prompt


def test_best_practices_included_only_for_create_new_spec() -> None:
    create_prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(target_spec_file="tests/new.spec.ts", create_new=True),
        action=PlaywrightTestActionDecision(action="create_new_spec"),
    )
    append_prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(target_spec_file="tests/plans.spec.ts"),
        action=PlaywrightTestActionDecision(action="append_new_test"),
    )
    assert "Playwright best practices for new specs" in create_prompt
    assert "Locator priority: getByRole" in create_prompt
    assert "Playwright best practices for new specs" not in append_prompt


def test_create_new_spec_uses_template_anchor_from_repository() -> None:
    orchestrator = GenerationOrchestrator()
    anchor = orchestrator._resolve_anchor_flow_context(
        placement=SpecPlacementDecision(target_spec_file="tests/new-area.spec.ts", create_new=True),
        action=PlaywrightTestActionDecision(action="create_new_spec"),
        candidates=[
            _anchor_unit("bare", 1),
            _anchor_unit("rich", 10, page_objects=["LoginPage"], fixtures=["page", "storageState"]),
        ],
    )
    assert anchor is not None
    assert anchor.anchor_test_title == "rich"
    assert "existing test(s) across the repository" in anchor.rationale


def test_ownership_prompt_includes_needed_locators_section() -> None:
    from worktop.test_agent.app.prompts.ownership_resolution_prompt import build_ownership_resolution_prompt
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
    from worktop.test_agent.app.schemas.source_intelligence import SourceEvidence, SourceIntelligence

    prompt = build_ownership_resolution_prompt(
        RepositoryInventory(repo_path="/tmp/repo", repo_head="abc"),
        SourceIntelligence(
            locator_evidence=[SourceEvidence(path="src/plan-tile.html", symbol="planDesignTile")]
        ),
        FunctionalIntent(capability="open plan design"),
    )
    assert "Needed locators and components (source evidence):" in prompt
    assert "planDesignTile" in prompt
    assert "not generically" in prompt


def test_ownership_emission_check_fails_without_promised_owner_patch() -> None:
    from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution

    orchestrator = GenerationOrchestrator()
    ownership = OwnershipResolution(
        owner_path="pages/PlanPage.ts",
        owner_kind="page_object",
        create_new=True,
    )
    patches = PatchSet(
        patches=[
            CodePatch(path="tests/plans.spec.ts", operation="append", content="test('x')")
        ]
    )
    check = orchestrator._ownership_emission_check(patches, ownership)
    assert check.passed is False
    assert "must create it" in check.output

    patches_with_owner = PatchSet(
        patches=[
            CodePatch(path="tests/plans.spec.ts", operation="append", content="test('x')"),
            CodePatch(path="pages/PlanPage.ts", operation="create", content="export class PlanPage {}"),
        ]
    )
    assert orchestrator._ownership_emission_check(patches_with_owner, ownership).passed is True


def test_ownership_emission_check_noop_for_reuse_or_spec_owner() -> None:
    from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution

    orchestrator = GenerationOrchestrator()
    reuse = OwnershipResolution(owner_path="pages/PlanPage.ts", owner_kind="page_object", create_new=False)
    spec_owner = OwnershipResolution(owner_path="spec", owner_kind="spec", create_new=True)
    empty = PatchSet(patches=[])
    assert orchestrator._ownership_emission_check(empty, reuse).passed is True
    assert orchestrator._ownership_emission_check(empty, spec_owner).passed is True
    assert orchestrator._ownership_emission_check(empty, None).passed is True


def test_reference_integrity_flags_unresolved_import(tmp_path) -> None:
    orchestrator = GenerationOrchestrator()
    (tmp_path / "tests").mkdir()
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="create",
                content="import { PlanPage } from '../pages/plan-page';\n",
            )
        ]
    )
    check = orchestrator._reference_integrity_check(patches, str(tmp_path))
    assert check.passed is False
    assert "does not resolve" in check.output


def test_reference_integrity_resolves_import_from_patch_set(tmp_path) -> None:
    orchestrator = GenerationOrchestrator()
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="create",
                content="import { PlanPage } from '../pages/plan-page';\n",
            ),
            CodePatch(
                path="pages/plan-page.ts",
                operation="create",
                content="export class PlanPage { async open() {} }",
            ),
        ]
    )
    check = orchestrator._reference_integrity_check(patches, str(tmp_path))
    assert check.passed is True


def test_reference_integrity_flags_invented_page_object_method(tmp_path) -> None:
    orchestrator = GenerationOrchestrator()
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "plan-page.ts").write_text(
        "export class PlanPage {\n  async openDesigner() {}\n}\n",
        encoding="utf-8",
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="create",
                content=(
                    "import { PlanPage } from '../pages/plan-page';\n"
                    "const planPage = new PlanPage(page);\n"
                    "await planPage.openDesigner();\n"
                    "await planPage.missingMethod();\n"
                ),
            )
        ]
    )
    check = orchestrator._reference_integrity_check(patches, str(tmp_path))
    assert check.passed is False
    assert "missingMethod" in check.output
    assert "openDesigner" not in check.output


def test_reference_integrity_skips_unresolvable_and_inherited_classes(tmp_path) -> None:
    orchestrator = GenerationOrchestrator()
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "base-page.ts").write_text(
        "export class BasePage extends CorePage {\n}\n",
        encoding="utf-8",
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="create",
                content=(
                    "import { BasePage } from '../pages/base-page';\n"
                    "const basePage = new BasePage(page);\n"
                    "await basePage.inheritedMethod();\n"
                    "const other = new UnimportedPage(page);\n"
                    "await other.anything();\n"
                ),
            )
        ]
    )
    check = orchestrator._reference_integrity_check(patches, str(tmp_path))
    assert check.passed is True


def test_created_spec_structure_check_requires_playwright_shape() -> None:
    orchestrator = GenerationOrchestrator()
    bad = PatchSet(
        patches=[
            CodePatch(
                path="tests/new.spec.ts",
                operation="create",
                content="console.log('not a test');",
            )
        ]
    )
    check = orchestrator._created_spec_structure_check(bad)
    assert check.passed is False
    assert "@playwright/test" in check.output

    good = PatchSet(
        patches=[
            CodePatch(
                path="tests/new.spec.ts",
                operation="create",
                content=(
                    "import { test, expect } from '@playwright/test';\n"
                    "test('proves behavior', async ({ page }) => {\n"
                    "  await expect(page).toHaveURL('/');\n"
                    "});\n"
                ),
            )
        ]
    )
    assert orchestrator._created_spec_structure_check(good).passed is True


def _write_package_json(tmp_path, dependencies=None, scripts=None) -> None:
    import json as _json

    (tmp_path / "package.json").write_text(
        _json.dumps(
            {
                "name": "demo-ui",
                "dependencies": dependencies or {},
                "scripts": scripts or {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_repo_strategy_classifies_greenfield_ui_repo_as_bootstrap(tmp_path) -> None:
    from worktop.test_agent.app.services.repo_strategy_service import RepoStrategyService

    _write_package_json(
        tmp_path,
        dependencies={"@angular/core": "^17.0.0"},
        scripts={"start": "ng serve"},
    )
    (tmp_path / "src").mkdir()

    profile = RepoStrategyService().detect(str(tmp_path))

    assert profile.support_status == "supported_with_warnings"
    assert profile.requires_bootstrap is True
    assert any("bootstrap" in warning.lower() for warning in profile.support_warnings)
    assert not profile.support_blockers


def test_repo_strategy_still_blocks_cypress_repo_without_playwright(tmp_path) -> None:
    from worktop.test_agent.app.services.repo_strategy_service import RepoStrategyService

    _write_package_json(tmp_path, dependencies={"react": "^18.0.0", "cypress": "^13.0.0"})

    profile = RepoStrategyService().detect(str(tmp_path))

    assert profile.support_status == "unsupported"
    assert profile.requires_bootstrap is False


def test_repo_strategy_config_without_specs_is_warning_not_blocker(tmp_path) -> None:
    from worktop.test_agent.app.services.repo_strategy_service import RepoStrategyService

    _write_package_json(tmp_path, dependencies={"react": "^18.0.0"})
    (tmp_path / "playwright.config.ts").write_text(
        "import { defineConfig } from '@playwright/test';\nexport default defineConfig({});\n",
        encoding="utf-8",
    )

    profile = RepoStrategyService().detect(str(tmp_path))

    assert profile.support_status == "supported_with_warnings"
    assert profile.requires_bootstrap is False
    assert not profile.support_blockers


def test_bootstrap_scaffold_builds_config_package_and_fixtures(tmp_path) -> None:
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile
    from worktop.test_agent.app.services.bootstrap_scaffold_service import BootstrapScaffoldService

    _write_package_json(
        tmp_path,
        dependencies={"@angular/core": "^17.0.0"},
        scripts={"start": "ng serve"},
    )
    profile = RepoProfile(
        repo_path=str(tmp_path),
        requires_bootstrap=True,
        detected_frameworks=["angular"],
        package_manager="npm",
        package_scripts={"start": "ng serve"},
    )

    patches = BootstrapScaffoldService().build_scaffold_patches(str(tmp_path), profile)
    by_path = {patch.path: patch for patch in patches}

    assert set(by_path) == {"playwright.config.ts", "package.json", "e2e/fixtures.ts"}
    config = by_path["playwright.config.ts"].content
    assert "testDir: './e2e'" in config
    assert "http://localhost:4200" in config
    assert "npm run start" in config
    package = by_path["package.json"].content
    assert "@playwright/test" in package
    assert "test:e2e" in package
    assert '"name": "demo-ui"' in package
    assert by_path["package.json"].operation == "replace"


def test_bootstrap_merge_prefers_deterministic_scaffold_on_collision(tmp_path) -> None:
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile
    from worktop.test_agent.app.services.bootstrap_scaffold_service import BootstrapScaffoldService

    _write_package_json(tmp_path, dependencies={"react": "^18.0.0"})
    profile = RepoProfile(
        repo_path=str(tmp_path),
        requires_bootstrap=True,
        detected_frameworks=["react"],
    )
    generated = PatchSet(
        patches=[
            CodePatch(
                path="playwright.config.ts",
                operation="create",
                content="// llm-invented config",
            ),
            CodePatch(
                path="e2e/orders.spec.ts",
                operation="create",
                content="import { test, expect } from '@playwright/test';\ntest('x', async ({ page }) => { await expect(page).toHaveURL('/'); });",
            ),
        ]
    )

    merged = BootstrapScaffoldService().merge(str(tmp_path), profile, generated)
    config_patches = [p for p in merged.patches if p.path == "playwright.config.ts"]

    assert len(config_patches) == 1
    assert "llm-invented" not in config_patches[0].content
    assert any(p.path == "e2e/orders.spec.ts" for p in merged.patches)


def test_bootstrap_placement_normalized_to_e2e_convention() -> None:
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile

    orchestrator = GenerationOrchestrator()
    profile = RepoProfile(repo_path="/tmp/repo", requires_bootstrap=True)
    placement = orchestrator._normalize_bootstrap_placement(
        profile,
        SpecPlacementDecision(target_spec_file="tests/orders.spec.ts", create_new=False),
    )
    assert placement.target_spec_file == "e2e/orders.spec.ts"
    assert placement.create_new is True

    untouched = orchestrator._normalize_bootstrap_placement(
        RepoProfile(repo_path="/tmp/repo", requires_bootstrap=False),
        SpecPlacementDecision(target_spec_file="tests/orders.spec.ts", create_new=False),
    )
    assert untouched.target_spec_file == "tests/orders.spec.ts"


def test_bootstrap_scaffold_guard_requires_config_and_dependency() -> None:
    orchestrator = GenerationOrchestrator()
    missing = PatchSet(
        patches=[
            CodePatch(
                path="e2e/orders.spec.ts",
                operation="create",
                content="import { test, expect } from '@playwright/test';",
            )
        ]
    )
    check = orchestrator._bootstrap_scaffold_check(missing, requires_bootstrap=True)
    assert check.passed is False
    assert "playwright.config" in check.output

    complete = PatchSet(
        patches=[
            CodePatch(path="playwright.config.ts", operation="create", content="export default {};"),
            CodePatch(
                path="package.json",
                operation="replace",
                start_line=1,
                end_line=5,
                content='{"devDependencies": {"@playwright/test": "^1.50.0"}}',
            ),
            CodePatch(
                path="e2e/orders.spec.ts",
                operation="create",
                content="import { test, expect } from '@playwright/test';",
            ),
        ]
    )
    assert orchestrator._bootstrap_scaffold_check(complete, requires_bootstrap=True).passed is True
    assert orchestrator._bootstrap_scaffold_check(missing, requires_bootstrap=False).passed is True


def test_response_contract_has_real_ownership_example() -> None:
    from worktop.test_agent.app.prompts.prompt_sections import response_contract
    from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution

    contract = response_contract(OwnershipResolution)

    assert '"owner_path": "e2e/pages/plan-page.ts"' in contract
    assert "reuse_existing_page_object" in contract
    assert "Valid response example:\n{}" not in contract


def test_response_contract_no_fabricated_example_for_unknown_model() -> None:
    from pydantic import BaseModel

    from worktop.test_agent.app.prompts.prompt_sections import response_contract

    class UnknownDecision(BaseModel):
        verdict: str

    contract = response_contract(UnknownDecision)

    assert "Valid response example" not in contract
    assert "No canonical example is available" in contract
    assert "JSON schema:" in contract


def test_patchset_contract_includes_labeled_action_examples() -> None:
    from worktop.test_agent.app.prompts.prompt_sections import response_contract

    contract = response_contract(PatchSet)

    assert "Valid response example (create_new_spec):" in contract
    assert "Valid response example (append_new_test (reuse the anchor flow's setup)):" in contract
    assert "extend_existing_test (exact replace of the selected block)" in contract
    assert '"operation": "replace"' in contract
    assert '"start_line": 10' in contract


def test_curated_inventory_strips_hashes_caps_lists_and_prioritizes_e2e() -> None:
    from worktop.test_agent.app.prompts.prompt_sections import curated_inventory
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
    from worktop.test_agent.app.schemas.test_file_classification import TestFileClassification

    inventory = RepositoryInventory(
        repo_path="/tmp/repo",
        repo_head="abc",
        file_hashes={f"src/file{i}.ts": f"hash{i}" for i in range(100)},
        test_files=[
            TestFileClassification(path="tests/unit.test.ts", kind="unit"),
            TestFileClassification(
                path="tests/plans.spec.ts", kind="e2e", is_e2e_candidate=True
            ),
        ],
        page_objects=[f"pages/page{i}.ts" for i in range(45)],
    )

    curated = curated_inventory(inventory, max_items=40)

    assert "file_hashes" not in curated
    assert len(curated["page_objects"]) == 40
    assert "5 more item(s) omitted" in curated["page_objects_omitted"]
    assert curated["test_files"][0]["path"] == "tests/plans.spec.ts"


def test_curated_test_units_caps_candidates_and_truncates_excerpts() -> None:
    from worktop.test_agent.app.prompts.prompt_sections import curated_test_units

    units = [
        BehavioralTestUnit(
            file_path="tests/plans.spec.ts",
            test_title=f"test {i}",
            start_line=i * 10 + 1,
            end_line=i * 10 + 5,
            source_excerpt="x" * 700,
        )
        for i in range(30)
    ]

    curated = curated_test_units(units, max_units=25, excerpt_chars=600)

    assert len(curated) == 26  # 25 units + omission note
    assert curated[0]["source_excerpt"].endswith("… [truncated]")
    assert len(curated[0]["source_excerpt"]) < 700
    assert "5 lower-ranked candidate(s) omitted" in curated[25]["note"]


def test_spec_placement_prompt_excludes_file_hashes() -> None:
    from worktop.test_agent.app.prompts.spec_placement_prompt import build_spec_placement_prompt
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory

    prompt = build_spec_placement_prompt(
        RepositoryInventory(
            repo_path="/tmp/repo",
            repo_head="abc",
            file_hashes={"src/app.ts": "deadbeef"},
        )
    )

    assert "file_hashes" not in prompt
    assert "deadbeef" not in prompt


def test_shallow_decision_trace_is_flagged_for_review() -> None:
    from worktop.test_agent.app.schemas.decision_trace import DecisionTrace

    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_shallow_decision_trace(
        "spec_placement", DecisionTrace(decision="undecided"), reasons
    )
    assert len(reasons) == 1
    assert "decision trace lacks" in reasons[0]

    reasons_missing_evidence: list[str] = []
    orchestrator._flag_shallow_decision_trace(
        "test_action",
        DecisionTrace(decision="append_new_test", justification="same module"),
        reasons_missing_evidence,
    )
    assert len(reasons_missing_evidence) == 1


def test_complete_decision_trace_is_not_flagged() -> None:
    from worktop.test_agent.app.schemas.decision_trace import DecisionTrace

    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_shallow_decision_trace(
        "spec_placement",
        DecisionTrace(
            decision="extend_existing_spec",
            justification="Existing spec owns the same route.",
            evidence=["tests/plans.spec.ts covers /plans"],
        ),
        reasons,
    )
    assert reasons == []


def test_repair_loop_rolls_back_repairs_and_revalidates() -> None:
    orchestrator = GenerationOrchestrator()
    patch_writer = FakePatchWriter()
    validator = FakeValidator()
    orchestrator.patch_writer = patch_writer
    orchestrator.validator = validator

    initial = PatchSet(
        patches=[
            CodePatch(
                path="tests/example.spec.ts",
                operation="replace",
                start_line=1,
                end_line=1,
                content="bad",
            )
        ]
    )
    repaired = PatchSet(
        patches=[
            CodePatch(
                path="tests/example.spec.ts",
                operation="replace",
                start_line=1,
                end_line=1,
                content="fixed",
            )
        ]
    )
    request = GenerationRequest(
        job_id="job-1",
        repo_path="/tmp/repo",
        tenant_id="tenant-1",
        test_case_name="repair flow",
        run_validation=True,
    )

    patch_result, validation, final_patches = orchestrator._write_validate_and_repair(
        request=request,
        patches=initial,
        ui_context=PlaywrightUiContext(),
        existing_test_context=None,
        critic=FakeCritic(),
        repair=FakeRepair(repaired),
    )

    assert validator.calls == 2
    assert patch_writer.apply_calls == 2
    assert patch_writer.rollback_calls == 1
    assert validation is not None
    assert validation.passed is True
    assert validation.repair_attempted is True
    assert final_patches == repaired
    assert patch_result.applied[0].path == "tests/example.spec.ts"


def test_playwright_parser_preserves_existing_test_source_excerpt() -> None:
    parser = PlaywrightParserTool()
    content = """
import { test, expect } from '@playwright/test';

test('opens plan design', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Plan Design' }).click();
  await expect(page).toHaveURL(/plan-design/);
});
"""

    units = parser.extract_tests("tests/plans.spec.ts", content)

    assert len(units) == 1
    assert units[0].source_excerpt.startswith("test('opens plan design'")
    assert "toHaveURL" in units[0].source_excerpt


def test_playwright_parser_ignores_tests_inside_comments_and_strings() -> None:
    parser = PlaywrightParserTool()
    content = """
import { test, expect } from '@playwright/test';

// test('commented test', async ({ page }) => {
//   await page.goto('/commented');
// });

const fixtureText = "test('string test', async ({ page }) => {})";

test('real test', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL('/');
});
"""

    units = parser.extract_tests("tests/plans.spec.ts", content)

    assert [unit.test_title for unit in units] == ["real test"]


def test_behavioral_inventory_rejects_invalid_parser_candidate_range() -> None:
    service = BehavioralInventoryService()
    content = """
import { test, expect } from '@playwright/test';

test('real test', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL('/');
});
"""
    bad_unit = BehavioralTestUnit(
        file_path="tests/plans.spec.ts",
        test_title="real test",
        start_line=1,
        end_line=1,
        source_excerpt="test('real test', async ({ page }) => {});",
    )

    validated = service._filter_integrity("tests/plans.spec.ts", content, [bad_unit])

    assert validated == []


def test_code_generation_prompt_includes_existing_test_context_contract() -> None:
    prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts",
            create_new=False,
        ),
        action=PlaywrightTestActionDecision(
            action="extend_existing_test",
            target_test_title="opens plan design",
        ),
        existing_test_context=ExistingTestContext(
            file_path="tests/plans.spec.ts",
            test_title="opens plan design",
            start_line=10,
            end_line=18,
            source_excerpt="test('opens plan design', async ({ page }) => {});",
        ),
    )

    assert "Existing test context:" in prompt
    assert "emit replace_test with the Existing test context file_path" in prompt
    assert '"start_line": 10' in prompt
    assert '"end_line": 18' in prompt
    assert "test('opens plan design'" in prompt


def test_code_generation_prompt_includes_flow_plan_and_ownership() -> None:
    from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan
    from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution

    prompt = build_code_generation_prompt(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts",
            create_new=False,
        ),
        action=PlaywrightTestActionDecision(
            action="append_new_test",
        ),
        flow_plan=FlowMergePlan(
            stable_region="login and navigate",
            extension_region="assert new banner",
            preserved_steps=["login"],
            added_steps=["expect banner"],
        ),
        ownership=OwnershipResolution(
            owner_path="pages/PlanPage.ts",
            owner_kind="page_object",
        ),
    )

    assert "Flow merge plan:" in prompt
    assert "Ownership resolution:" in prompt
    assert "stable_region" in prompt
    assert "pages/PlanPage.ts" in prompt
    assert "keep its stable_region and preserved_steps intact" in prompt
    assert "place new locators, helpers, and methods in the resolved owner" in prompt


def test_existing_test_context_resolves_selected_extension_target() -> None:
    orchestrator = GenerationOrchestrator()
    target = orchestrator._resolve_existing_test_context(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts",
            create_new=False,
        ),
        action=PlaywrightTestActionDecision(
            action="extend_existing_test",
            target_test_title="opens plan design",
        ),
        candidates=[
            BehavioralTestUnit(
                file_path="tests/plans.spec.ts",
                test_title="opens plan design",
                start_line=10,
                end_line=18,
                source_excerpt="test('opens plan design', async ({ page }) => {});",
            )
        ],
    )

    assert target is not None
    assert target.file_path == "tests/plans.spec.ts"
    assert target.start_line == 10
    assert target.end_line == 18
    assert target.source_excerpt.startswith("test(")


def test_reconcile_coerces_extend_to_create_when_placement_creates_new_spec() -> None:
    orchestrator = GenerationOrchestrator()
    action = orchestrator._reconcile_action_with_placement(
        placement=SpecPlacementDecision(
            target_spec_file="tests/generated.spec.ts",
            create_new=True,
        ),
        action=PlaywrightTestActionDecision(
            action="extend_existing_test",
            target_test_title="opens plan design",
            confidence=0.88,
        ),
    )

    assert action.action == "create_new_spec"
    assert action.target_test_title is None
    assert action.confidence <= 0.4


def test_reconcile_coerces_new_spec_action_to_append_when_placement_reuses() -> None:
    orchestrator = GenerationOrchestrator()
    action = orchestrator._reconcile_action_with_placement(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts",
            create_new=False,
        ),
        action=PlaywrightTestActionDecision(
            action="create_new_spec",
            confidence=0.9,
        ),
    )

    assert action.action == "append_new_test"
    assert action.confidence <= 0.4


def test_reconcile_leaves_consistent_decisions_untouched() -> None:
    orchestrator = GenerationOrchestrator()
    original = PlaywrightTestActionDecision(
        action="extend_existing_test",
        target_test_title="opens plan design",
        confidence=0.82,
    )
    reconciled = orchestrator._reconcile_action_with_placement(
        placement=SpecPlacementDecision(
            target_spec_file="tests/plans.spec.ts",
            create_new=False,
        ),
        action=original,
    )

    assert reconciled is original


def test_low_placement_confidence_is_flagged_for_review() -> None:
    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    orchestrator._flag_low_placement_confidence(
        SpecPlacementDecision(target_spec_file="tests/plans.spec.ts", confidence=0.2),
        reasons,
    )
    assert len(reasons) == 1
    assert "confidence" in reasons[0]


def test_low_confidence_extension_downgrades_to_append_and_flags() -> None:
    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    action = orchestrator._gate_action_confidence(
        PlaywrightTestActionDecision(
            action="extend_existing_test",
            target_test_title="opens plan design",
            confidence=0.2,
        ),
        reasons,
    )
    assert action.action == "append_new_test"
    assert action.target_test_title is None
    assert reasons and "confidence" in reasons[0]


def test_low_confidence_append_is_flagged_but_kept() -> None:
    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    action = orchestrator._gate_action_confidence(
        PlaywrightTestActionDecision(action="append_new_test", confidence=0.1),
        reasons,
    )
    assert action.action == "append_new_test"
    assert len(reasons) == 1


def test_high_confidence_action_is_not_flagged() -> None:
    orchestrator = GenerationOrchestrator()
    reasons: list[str] = []
    original = PlaywrightTestActionDecision(
        action="extend_existing_test",
        target_test_title="opens plan design",
        confidence=0.95,
    )
    action = orchestrator._gate_action_confidence(original, reasons)
    assert action is original
    assert reasons == []


def test_result_builder_marks_needs_review_when_reasons_present() -> None:
    from worktop.test_agent.app.services.result_builder_service import ResultBuilderService

    request = GenerationRequest(
        job_id="job-1",
        repo_path="/tmp/repo",
        tenant_id="tenant-1",
        test_case_name="review flow",
    )
    result = ResultBuilderService().build(
        request=request,
        patches=PatchSet(patches=[]),
        patch_result=PatchWriteResult(),
        validation=None,
        review_reasons=["low placement confidence"],
    )
    assert result.needs_review is True
    assert result.review_reasons == ["low placement confidence"]


def test_unsafe_extension_action_downgrades_when_no_valid_context_exists() -> None:
    orchestrator = GenerationOrchestrator()
    action = orchestrator._ensure_safe_extension_action(
        PlaywrightTestActionDecision(
            action="extend_existing_test",
            target_test_title="missing target",
            confidence=0.91,
        ),
        existing_test_context=None,
    )

    assert action.action == "append_new_test"
    assert action.target_test_title is None
    assert action.confidence == 0.35
    assert action.decision_trace.decision == "append_new_test"


def test_extension_patch_guard_repairs_before_writing_wrong_range(tmp_path) -> None:
    orchestrator = GenerationOrchestrator()
    patch_writer = FakePatchWriter()
    validator = FakePassingValidator()
    orchestrator.patch_writer = patch_writer
    orchestrator.validator = validator

    initial = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                start_line=16,
                content="await expect(page).toHaveURL(/plan-design/);",
            )
        ]
    )
    repaired = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="replace",
                start_line=10,
                end_line=18,
                content=(
                    "test('opens plan design', async ({ page }) => {\n"
                    "  await page.goto('/');\n"
                    "  await expect(page).toHaveURL(/plan-design/);\n"
                    "});"
                ),
            )
        ]
    )
    target = tmp_path / "tests" / "plans.spec.ts"
    target.parent.mkdir()
    target.write_text(
        """import { test, expect } from '@playwright/test';
test.describe('plans', () => {
  test('opens plan design', async ({ page }) => {
    await page.goto('/');
  });
});
""",
        encoding="utf-8",
    )
    request = GenerationRequest(
        job_id="job-1",
        repo_path=str(tmp_path),
        tenant_id="tenant-1",
        test_case_name="repair extension",
        run_validation=True,
    )

    patch_result, validation, final_patches = orchestrator._write_validate_and_repair(
        request=request,
        patches=initial,
        ui_context=PlaywrightUiContext(),
        existing_test_context=ExistingTestContext(
                file_path="tests/plans.spec.ts",
                describe_title="plans",
                test_title="opens plan design",
                start_line=3,
                end_line=5,
                source_excerpt="test('opens plan design', async ({ page }) => { await page.goto('/'); });",
        ),
        critic=FakeCritic(),
        repair=FakeRepair(repaired),
    )

    assert patch_writer.apply_calls == 1
    assert patch_writer.applied_patch_sets == [repaired]
    assert validator.calls == 1
    assert validation is not None
    assert validation.passed is True
    assert final_patches == repaired
    assert patch_result.applied[0].operation == "replace_test"


class FakePatchWriter:
    def __init__(self) -> None:
        self.apply_calls = 0
        self.rollback_calls = 0
        self.applied_patch_sets: list[PatchSet] = []

    def apply(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        self.apply_calls += 1
        self.applied_patch_sets.append(patches)
        return PatchWriteResult(
            applied=[
                AppliedPatch(
                    path=patches.patches[0].path,
                    operation=patches.patches[0].operation,
                    diff="diff",
                )
            ]
        )

    def rollback(self, repo_path: str, result: PatchWriteResult) -> None:
        self.rollback_calls += 1


class FakeValidator:
    def __init__(self) -> None:
        self.calls = 0

    def validate(
        self,
        repo_path: str,
        patches: PatchSet,
        ui_context: PlaywrightUiContext,
    ) -> ValidationResult:
        self.calls += 1
        return ValidationResult(
            passed=self.calls > 1,
            checks=[
                ValidationCheck(
                    name="fake_validation",
                    passed=self.calls > 1,
                    output="ok" if self.calls > 1 else "failed",
                )
            ],
        )


class FakePassingValidator:
    def __init__(self) -> None:
        self.calls = 0

    def validate(
        self,
        repo_path: str,
        patches: PatchSet,
        ui_context: PlaywrightUiContext,
    ) -> ValidationResult:
        self.calls += 1
        return ValidationResult(
            passed=True,
            checks=[
                ValidationCheck(
                    name="fake_validation",
                    passed=True,
                    output="ok",
                )
            ],
        )


class FakeRepair:
    def __init__(self, repaired: PatchSet) -> None:
        self.repaired = repaired

    def repair(
        self, patches: PatchSet, validation: ValidationResult, anchor=None, locator_decisions=None
    ) -> PatchSet:
        return self.repaired


class FakeCritic:
    def review(
        self,
        patches: PatchSet,
        ui_context: PlaywrightUiContext,
        anchor=None,
        locator_decisions=None,
    ) -> PatchSet:
        return patches


def test_repo_strategy_bootstraps_unrecognized_framework_with_dev_script(tmp_path) -> None:
    from worktop.test_agent.app.services.repo_strategy_service import RepoStrategyService

    # No Angular/React signal at all — just a runnable dev server script.
    _write_package_json(
        tmp_path,
        dependencies={"some-internal-ui-kit": "^1.0.0"},
        scripts={"dev": "vite"},
    )
    (tmp_path / "src").mkdir()

    profile = RepoStrategyService().detect(str(tmp_path))

    assert profile.support_status == "supported_with_warnings"
    assert profile.requires_bootstrap is True
    assert not profile.support_blockers


def test_spec_placement_agent_explores_before_deciding(tmp_path) -> None:
    from worktop.test_agent.app.agents.spec_placement_agent import SpecPlacementAgent
    from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "plans.spec.ts").write_text(
        "import { test } from '@playwright/test';", encoding="utf-8"
    )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def complete_structured(self, prompt, response_model):
            self.calls += 1
            if self.calls == 1:
                return response_model.model_validate({
                    "reasoning": "Need to confirm tests/plans.spec.ts owns the plan flow.",
                    "requests": [{"kind": "read_file", "target": "tests/plans.spec.ts",
                                  "reason": "verify ownership before placing"}],
                })
            assert "@playwright/test" in prompt  # evidence fed back
            return response_model.model_validate({
                "reasoning": "Confirmed ownership from file content.",
                "requests": [],
                "output": {"target_spec_file": "tests/plans.spec.ts",
                           "create_new": False, "confidence": 0.9},
            })

    agent = SpecPlacementAgent(llm_client=FakeLLM())
    decision = agent.decide(
        RepositoryInventory(repo_path=str(tmp_path), repo_head="abc")
    )
    assert agent.llm.calls == 2
    assert decision.target_spec_file == "tests/plans.spec.ts"


def test_strategy_report_greenfield_no_evidence() -> None:
    from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile
    from worktop.test_agent.app.services.playwright_ui_intelligence_service import (
        PlaywrightUiIntelligenceService,
    )

    svc = PlaywrightUiIntelligenceService()
    report = svc._log_strategy_report(
        PlaywrightUiContext(),
        RepoProfile(repo_path="/tmp/repo", requires_bootstrap=True),
    )
    assert report["greenfield"] == "true"
    assert report["evidence_tier"] == "none"
    assert report["auth_basis"].startswith("best_practices_fallback")
    assert report["network_basis"] == "no_network_endpoints_detected"
    assert report["mock_basis"].startswith("no_mocks_detected")


def test_strategy_report_source_only_mixed_network() -> None:
    from worktop.test_agent.app.schemas.playwright_ui_context import (
        AuthSessionEvidence,
        MockPatternEvidence,
        PlaywrightUiContext,
        UiRouteEvidence,
    )
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile
    from worktop.test_agent.app.services.playwright_ui_intelligence_service import (
        PlaywrightUiIntelligenceService,
    )

    ctx = PlaywrightUiContext(
        routes=[
            UiRouteEvidence(path="/api/orders", file_path="src/routes.ts"),
            UiRouteEvidence(path="/graphql", file_path="src/apollo.ts"),
        ],
        auth_session_patterns=[
            AuthSessionEvidence(kind="storage_state", file_path="src/auth.ts")
        ],
        mock_patterns=[
            MockPatternEvidence(kind="msw_or_network_handler", file_path="src/mocks.ts")
        ],
    )
    svc = PlaywrightUiIntelligenceService()
    report = svc._log_strategy_report(ctx, RepoProfile(repo_path="/tmp/repo"))
    assert report["greenfield"] == "true"  # no existing specs
    assert report["evidence_tier"] == "source_only"
    assert report["auth_basis"] == "reuse_detected:storage_state"
    assert report["network_basis"] == "mixed_rest_and_graphql_detected"
    assert report["mock_basis"].startswith("reuse_detected:")


def test_strategy_report_existing_tests_tier() -> None:
    from worktop.test_agent.app.schemas.playwright_ui_context import (
        ExistingSpecPattern,
        PlaywrightUiContext,
    )
    from worktop.test_agent.app.schemas.repo_profile import RepoProfile
    from worktop.test_agent.app.services.playwright_ui_intelligence_service import (
        PlaywrightUiIntelligenceService,
    )

    ctx = PlaywrightUiContext(
        existing_spec_patterns=[ExistingSpecPattern(file_path="tests/plans.spec.ts")]
    )
    svc = PlaywrightUiIntelligenceService()
    report = svc._log_strategy_report(ctx, RepoProfile(repo_path="/tmp/repo"))
    assert report["greenfield"] == "false"
    assert report["evidence_tier"] == "existing_tests"
