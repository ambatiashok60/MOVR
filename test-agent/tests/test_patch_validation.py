from pathlib import Path

import pytest

from worktop.test_agent.app.patching.scoped_patch_writer import ScopedPatchWriter
from worktop.test_agent.app.schemas.code_patch import CodePatch, PatchSet
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext
from worktop.test_agent.app.services.generation_orchestrator import GenerationOrchestrator
from worktop.test_agent.app.validation.playwright_ui_quality_validator import (
    PlaywrightUiQualityValidator,
)
from worktop.test_agent.app.validation.playwright_validator import PlaywrightValidator


SPEC = """import { test, expect } from '@playwright/test';

test.describe('plans', () => {
  test('opens a plan', async ({ page }) => {
    await expect(page).toHaveURL(/plans/);
  });
});
"""


def _append_patch(title: str) -> PatchSet:
    return PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                content=(
                    f"  test('{title}', async ({{ page }}) => {{\n"
                    "    await expect(page).toHaveURL(/plans/);\n"
                    "  });\n"
                ),
            )
        ]
    )


def test_append_inserts_complete_test_inside_describe(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(SPEC, encoding="utf-8")

    patches = _append_patch("saves a plan")
    ScopedPatchWriter().apply(str(tmp_path), patches)

    content = path.read_text(encoding="utf-8")
    assert content.index("saves a plan") < content.rindex("});")
    assert PlaywrightValidator().validate(str(tmp_path), patches).passed
    assert not path.with_suffix(".ts.bak").exists()


def test_append_is_bound_to_anchor_describe(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(
        """import { test } from '@playwright/test';
test.describe('first suite', () => {
  test('first flow', async () => {});
});
test.describe('anchor suite', () => {
  test('anchor flow', async () => {});
});
""",
        encoding="utf-8",
    )
    patches = _append_patch("new branch")
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        describe_title="anchor suite",
        anchor_test_title="anchor flow",
        behavior_summary="Open the plan and reuse its setup.",
        source_excerpt="test('anchor flow', async () => {});",
    )

    failure = GenerationOrchestrator.__new__(
        GenerationOrchestrator
    )._bind_append_to_anchor_describe(patches, anchor, str(tmp_path))
    assert failure is None
    assert patches.patches[0].operation == "insert_test_after_anchor"
    assert patches.patches[0].target_test_title == "anchor flow"
    assert patches.patches[0].target_describe_title == "anchor suite"
    assert patches.patches[0].start_line is None
    ScopedPatchWriter().apply(str(tmp_path), patches)

    content = path.read_text(encoding="utf-8")
    anchor_suite = content[content.index("anchor suite") :]
    assert "new branch" in anchor_suite
    assert anchor_suite.index("anchor flow") < anchor_suite.index("new branch")


def test_append_test_resolves_fresh_structural_describe_offset(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(
        """import { test } from '@playwright/test';
test.describe('first suite', () => {
  test('first flow', async () => {});
});

// Lines may move after planning; describe identity remains stable.
test.describe('target suite', () => {
  test('anchor flow', async () => {});
});
""",
        encoding="utf-8",
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append_test",
                target_describe_title="target suite",
                content="  test('new structural flow', async () => {});",
            )
        ]
    )

    ScopedPatchWriter().apply(str(tmp_path), patches)

    content = path.read_text(encoding="utf-8")
    first_suite, target_suite = content.split("test.describe('target suite'", 1)
    assert "new structural flow" not in first_suite
    assert "new structural flow" in target_suite
    assert PlaywrightValidator().validate(str(tmp_path), patches).passed


def test_append_rejects_duplicate_test_name_before_write(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(SPEC, encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        ScopedPatchWriter().apply(str(tmp_path), _append_patch("opens a plan"))

    assert path.read_text(encoding="utf-8") == SPEC


def test_prewrite_duplicate_finding_can_enter_repair_loop(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(SPEC, encoding="utf-8")

    check = GenerationOrchestrator.__new__(GenerationOrchestrator)._append_integration_check(
        _append_patch("opens a plan"),
        str(tmp_path),
    )

    assert not check.passed
    assert "rename only the generated test" in check.output


def test_append_requires_anchor_flow_as_uninterrupted_block() -> None:
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        anchor_test_title="opens plan",
        source_excerpt=(
            "test('opens plan', async ({ page }) => {\n"
            "  await page.goto('/plans');\n"
            "  await page.getByRole('link', { name: 'Plan' }).click();\n"
            "});"
        ),
    )
    interrupted = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                content=(
                    "test('new branch', async ({ page }) => {\n"
                    "  // Anchor flow: opens plan\n"
                    "  await page.goto('/plans');\n"
                    "  await page.getByText('New').click();\n"
                    "  await page.getByRole('link', { name: 'Plan' }).click();\n"
                    "  // End anchor flow; new scenario steps begin below.\n"
                    "});"
                ),
            )
        ]
    )

    check = GenerationOrchestrator.__new__(GenerationOrchestrator)._append_reuse_check(
        interrupted, anchor
    )

    assert check.passed
    assert "Non-blocking anchor reuse warning" in check.output


def test_validator_only_checks_the_patch_target(tmp_path: Path) -> None:
    target = tmp_path / "tests" / "plans.spec.ts"
    target.parent.mkdir()
    target.write_text(SPEC, encoding="utf-8")
    unrelated = tmp_path / "tests" / "unrelated.spec.ts"
    unrelated.write_text(SPEC.replace("opens a plan", "duplicate") * 2, encoding="utf-8")

    patches = PatchSet(
        patches=[CodePatch(path="tests/plans.spec.ts", operation="replace", content=SPEC)]
    )

    assert PlaywrightValidator().validate(str(tmp_path), patches).passed


def test_quality_findings_are_non_blocking() -> None:
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="create",
                content="test('weak', async ({ page }) => { await page.waitForTimeout(100); });",
            )
        ]
    )

    check = PlaywrightUiQualityValidator().validate(patches)

    assert check.passed
    assert "Quality warnings (non-blocking)" in check.output


def test_semantic_supporting_patches_and_spec_patch_write_transactionally(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    tests = tmp_path / "tests"
    pages.mkdir()
    tests.mkdir()
    page = pages / "PlanPage.ts"
    locators = pages / "planLocators.ts"
    spec = tests / "plans.spec.ts"
    page.write_text("export class PlanPage {\n}\n", encoding="utf-8")
    locators.write_text("export const planLocators = {\n};\n", encoding="utf-8")
    spec.write_text(SPEC, encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="pages/PlanPage.ts",
                operation="insert_class_member",
                target_symbol="PlanPage",
                member_name="savePlan",
                content="  async savePlan() { return true; }",
            ),
            CodePatch(
                path="pages/planLocators.ts",
                operation="insert_object_property",
                target_symbol="planLocators",
                member_name="saveButton",
                content="  saveButton: 'button',",
            ),
            _append_patch("saves a plan").patches[0],
        ]
    )

    ScopedPatchWriter().apply(str(tmp_path), patches)

    assert page.read_text(encoding="utf-8").index("savePlan") < page.read_text(encoding="utf-8").rindex("}")
    assert locators.read_text(encoding="utf-8").index("saveButton") < locators.read_text(encoding="utf-8").rindex("}")
    assert PlaywrightValidator().validate(str(tmp_path), patches).passed


def test_invalid_supporting_patch_writes_nothing(tmp_path: Path) -> None:
    page = tmp_path / "PlanPage.ts"
    page.write_text("export class PlanPage {\n}\n", encoding="utf-8")
    original = page.read_text(encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="PlanPage.ts",
                operation="insert_class_member",
                target_symbol="PlanPage",
                member_name="validMethod",
                content="  validMethod() {}",
            ),
            CodePatch(
                path="PlanPage.ts",
                operation="insert_class_member",
                target_symbol="MissingPage",
                member_name="brokenMethod",
                content="  brokenMethod() {}",
            ),
        ]
    )

    with pytest.raises(ValueError, match="MissingPage"):
        ScopedPatchWriter().apply(str(tmp_path), patches)

    assert page.read_text(encoding="utf-8") == original


ANCHOR_SPEC = """import { test } from '@playwright/test';
test.describe('anchor suite', () => {
  test('anchor flow', async () => {});

  test('later sibling', async () => {});
});
"""


def test_insert_test_after_anchor_inserts_directly_after_anchor_block(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(ANCHOR_SPEC, encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="insert_test_after_anchor",
                target_test_title="anchor flow",
                target_describe_title="anchor suite",
                content="  test('new branch', async () => {});",
            )
        ]
    )

    ScopedPatchWriter().apply(str(tmp_path), patches)

    content = path.read_text(encoding="utf-8")
    assert content.index("anchor flow") < content.index("new branch")
    assert content.index("new branch") < content.index("later sibling")
    assert PlaywrightValidator().validate(str(tmp_path), patches).passed


def test_insert_test_after_anchor_rejects_unresolvable_anchor(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(ANCHOR_SPEC, encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="insert_test_after_anchor",
                target_test_title="anchor flow",
                target_describe_title="a different suite",
                content="  test('new branch', async () => {});",
            )
        ]
    )

    with pytest.raises(ValueError, match="Expected exactly one test"):
        ScopedPatchWriter().apply(str(tmp_path), patches)

    assert path.read_text(encoding="utf-8") == ANCHOR_SPEC


def test_bind_falls_back_to_describe_when_anchor_unresolvable(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(ANCHOR_SPEC, encoding="utf-8")
    patches = _append_patch("new branch")
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        describe_title="anchor suite",
        anchor_test_title="a renamed anchor that no longer exists",
    )

    failure = GenerationOrchestrator.__new__(
        GenerationOrchestrator
    )._bind_append_to_anchor_describe(patches, anchor, str(tmp_path))

    assert failure is None
    assert patches.patches[0].operation == "append_test"
    assert patches.patches[0].target_describe_title == "anchor suite"


TWO_DESCRIBE_SPEC = """import { test } from '@playwright/test';
test.describe('first suite', () => {
  test('first flow', async () => {});
});
test.describe('second suite', () => {
  test('second flow', async () => {});
});
"""


def test_unresolvable_anchor_is_blocking_plan_guard_failure(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(TWO_DESCRIBE_SPEC, encoding="utf-8")
    patches = _append_patch("new branch")
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        describe_title="a suite that does not exist",
        anchor_test_title="a test that does not exist",
    )
    orchestrator = GenerationOrchestrator.__new__(GenerationOrchestrator)

    failure = orchestrator._bind_append_to_anchor_describe(
        patches, anchor, str(tmp_path)
    )
    assert failure is not None
    assert "could not be structurally resolved" in failure
    assert "first suite" in failure and "second suite" in failure
    assert "first flow" in failure and "second flow" in failure

    result = orchestrator._patch_plan_check(
        patches,
        existing_test_context=None,
        anchor_flow_context=anchor,
        flow_plan=None,
        repo_path=str(tmp_path),
    )
    anchor_check = next(
        check for check in result.checks if check.name == "anchor_binding"
    )
    assert not anchor_check.passed
    assert not result.passed


def test_unresolvable_anchor_rebinds_to_sole_describe(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(ANCHOR_SPEC, encoding="utf-8")
    patches = _append_patch("new branch")
    anchor = AnchorFlowContext(
        file_path="tests/plans.spec.ts",
        describe_title="a suite that does not exist",
        anchor_test_title="a test that does not exist",
    )
    orchestrator = GenerationOrchestrator.__new__(GenerationOrchestrator)

    failure = orchestrator._bind_append_to_anchor_describe(
        patches, anchor, str(tmp_path)
    )
    assert failure is None
    assert patches.patches[0].operation == "append_test"
    assert patches.patches[0].target_describe_title == "anchor suite"
    assert patches.patches[0].target_test_title is None

    second = orchestrator._bind_append_to_anchor_describe(
        patches, anchor, str(tmp_path)
    )
    assert second is None
    assert patches.patches[0].operation == "append_test"
    assert patches.patches[0].target_describe_title == "anchor suite"

    ScopedPatchWriter().apply(str(tmp_path), patches)
    assert "new branch" in path.read_text(encoding="utf-8")


def test_writer_structural_outcome_blocks_count_mismatch(tmp_path: Path) -> None:
    writer = ScopedPatchWriter()
    patch = CodePatch(
        path="tests/plans.spec.ts",
        operation="append_test",
        target_describe_title="plans",
        content="  test('vanished', async () => {});",
    )

    with pytest.raises(ValueError, match="structural_outcome"):
        writer._assert_structural_outcome(patch, SPEC, SPEC)


def test_writer_structural_outcome_blocks_replace_count_change(
    tmp_path: Path,
) -> None:
    writer = ScopedPatchWriter()
    patch = CodePatch(
        path="tests/plans.spec.ts",
        operation="replace_test",
        target_test_title="opens a plan",
        content="test('opens a plan', async () => {});",
    )
    after_with_extra = SPEC + "test('stray extra', async () => {});\n"

    with pytest.raises(ValueError, match="structural_outcome"):
        writer._assert_structural_outcome(patch, SPEC, after_with_extra)


def test_validator_flags_missing_generated_title(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(SPEC, encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append_test",
                target_describe_title="plans",
                content="  test('never actually written', async () => {});",
            )
        ]
    )

    check = PlaywrightValidator().validate(str(tmp_path), patches)

    assert not check.passed
    assert "never actually written" in check.output


def test_validator_flags_generated_test_outside_target_describe(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(SPEC, encoding="utf-8")
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append_test",
                target_describe_title="a different suite",
                content="  test('opens a plan', async () => {});",
            )
        ]
    )

    check = PlaywrightValidator().validate(str(tmp_path), patches)

    assert not check.passed
    assert "a different suite" in check.output


def test_replace_test_resolves_fresh_structural_offsets(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir()
    path.write_text(
        """import { test } from '@playwright/test';
test.describe('plans', () => {
  test('neighbor', async () => {});
  test('target', async ({ page }) => {
    await page.goto('/old');
  });
});
""",
        encoding="utf-8",
    )
    parser = ScopedPatchWriter().playwright_parser
    _, _, expected = parser.find_test_block(
        "tests/plans.spec.ts", path.read_text(encoding="utf-8"), "target", "plans"
    )
    patches = PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="replace_test",
                target_test_title="target",
                target_describe_title="plans",
                expected_source=expected,
                content=(
                    "test('target', async ({ page }) => {\n"
                    "  await page.goto('/new');\n"
                    "});"
                ),
            )
        ]
    )

    ScopedPatchWriter().apply(str(tmp_path), patches)

    content = path.read_text(encoding="utf-8")
    assert "test('neighbor'" in content
    assert "page.goto('/new')" in content
    assert "page.goto('/old')" not in content
