from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def as_json(data: Any) -> str:
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    return json.dumps(data, indent=2, default=str)


def response_contract(response_model: type[BaseModel]) -> str:
    schema = response_model.model_json_schema()
    examples = _response_examples(response_model.__name__)
    return (
        "Return only valid JSON. Do not include markdown fences or prose.\n"
        "Return exactly one JSON object that validates against this Pydantic "
        f"model: {response_model.__name__}.\n"
        "Use only fields from the schema. Do not add explanatory text outside "
        "the JSON object.\n"
        "Do not invent extra keys. If evidence is missing, use an empty string, "
        "empty array, null, or conservative low confidence according to the schema.\n"
        "All generated code must be inside a schema field, never outside the JSON.\n"
        "For arrays whose item type is string, return strings only, not nested "
        "objects.\n"
        "Valid example for a string array: [\"Open dashboard\", \"Verify status\"]\n"
        "Invalid example for a string array: [{\"step\": \"Open dashboard\"}]\n\n"
        f"{examples}\n"
        "JSON schema:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _cap_list_fields(data: dict[str, Any], fields: tuple[str, ...], max_items: int) -> dict[str, Any]:
    for field in fields:
        items = data.get(field)
        if isinstance(items, list) and len(items) > max_items:
            omitted = len(items) - max_items
            data[field] = items[:max_items]
            data[f"{field}_omitted"] = f"{omitted} more item(s) omitted for brevity"
    return data


def curated_inventory(inventory: Any, max_items: int = 40) -> dict[str, Any]:
    """Repository inventory shaped for prompts.

    Drops per-file hashes (cache bookkeeping, useless to the model) and caps the
    file lists so a large repo cannot flood the context window. E2E candidate
    specs are kept ahead of other test files when capping.
    """
    if inventory is None:
        return {}
    data = inventory.model_dump(exclude={"file_hashes"})
    test_files = data.get("test_files")
    if isinstance(test_files, list):
        data["test_files"] = sorted(
            test_files,
            key=lambda item: not bool(item.get("is_e2e_candidate")),
        )
    return _cap_list_fields(
        data, ("test_files", "page_objects", "fixtures", "helpers"), max_items
    )


def curated_ui_context(ui_context: Any, max_items: int = 40) -> dict[str, Any]:
    """Playwright UI context shaped for prompts, with every evidence list capped."""
    if ui_context is None:
        return {}
    data = ui_context.model_dump()
    return _cap_list_fields(
        data,
        (
            "routes",
            "ui_elements",
            "mock_patterns",
            "auth_session_patterns",
            "test_data_patterns",
            "existing_spec_patterns",
            "ci_commands",
            "page_objects",
            "fixtures",
            "helpers",
            "quality_requirements",
        ),
        max_items,
    )


def curated_test_units(
    units: list[Any],
    max_units: int = 25,
    excerpt_chars: int = 600,
) -> list[dict[str, Any]]:
    """Behavioral test units shaped for prompts.

    Preserves ranking order, caps the number of candidates, and truncates long
    source excerpts. Never use this for an extend target's ExistingTestContext —
    that excerpt must stay complete because it is the replace source.
    """
    curated: list[dict[str, Any]] = []
    for unit in units[:max_units]:
        data = unit.model_dump()
        excerpt = data.get("source_excerpt") or ""
        if len(excerpt) > excerpt_chars:
            data["source_excerpt"] = f"{excerpt[:excerpt_chars]}… [truncated]"
        curated.append(data)
    if len(units) > max_units:
        curated.append(
            {"note": f"{len(units) - max_units} lower-ranked candidate(s) omitted for brevity"}
        )
    return curated


def playwright_best_practices() -> str:
    """Modern Playwright standards used when creating a new spec.

    This is the governing standard when the repository has no existing specs,
    page objects, or fixtures to reuse; when repo conventions exist they win.
    """
    return (
        "Playwright best practices for new specs (repo conventions take precedence "
        "when they exist):\n"
        "- Locator priority: getByRole with accessible name, then getByLabel, "
        "getByPlaceholder, getByText, then getByTestId; never raw CSS/XPath.\n"
        "- Use web-first assertions (await expect(locator).toHaveText/It auto-waits); "
        "never waitForTimeout, arbitrary timeouts, or networkidle.\n"
        "- Assert user-visible outcomes (URL, text, state), not implementation "
        "details.\n"
        "- Keep each test independent and parallel-safe: no shared mutable state, "
        "no ordering assumptions; use test.describe for grouping related tests.\n"
        "- Reuse auth via storageState or a beforeEach login flow; never re-derive "
        "auth inline per assertion.\n"
        "- Use test.step to structure long flows for readable CI reports.\n"
        "- Extract locators and interactions into a page object when more than one "
        "test will touch the same screen; otherwise keep the spec self-contained.\n"
        "- Name tests after the user-visible behavior they prove."
    )


def _response_examples(model_name: str) -> str:
    examples: dict[str, tuple[Any, Any]] = {
        "FunctionalIntent": (
            {
                "capability": "Plan design navigation",
                "actor": "Planner",
                "journey": ["Open landing page", "Click Plan Design tile"],
                "state_transitions": [
                    "Landing Page -> Plan Design Page; trigger: Click Plan Design tile; expected outcome: URL changes"
                ],
                "assertions": ["Verify current URL matches the plan design route"],
            },
            {
                "state_transitions": [
                    {
                        "from_state": "Landing Page",
                        "to_state": "Plan Design Page",
                    }
                ],
                "assertions": [{"type": "navigation", "description": "Verify URL"}],
            },
        ),
        "PatchSet": (
            [
                (
                    "create_new_spec",
                    {
                        "patches": [
                            {
                                "path": "e2e/plan-design.spec.ts",
                                "operation": "create",
                                "start_line": None,
                                "end_line": None,
                                "content": "import { test, expect } from '@playwright/test';\n\ntest('opens plan design', async ({ page }) => {\n  await page.goto('/');\n  await page.getByRole('button', { name: 'Plan Design' }).click();\n  await expect(page).toHaveURL(/plan-design/);\n});\n",
                                "reason": "Creates Playwright coverage for the requested navigation flow.",
                            }
                        ]
                    },
                ),
                (
                    "append_new_test (reuse the anchor flow's setup)",
                    {
                        "patches": [
                            {
                                "path": "tests/plans.spec.ts",
                                "operation": "append",
                                "start_line": None,
                                "end_line": None,
                                "content": "\ntest('shows saved badge after saving a plan', async ({ page }) => {\n  const planPage = new PlanPage(page);\n  await planPage.open();\n  await planPage.save();\n  await expect(page.getByText('Saved')).toBeVisible();\n});\n",
                                "reason": "Appends a new test reusing the anchor test's PlanPage setup; adds only the new saved-badge behavior.",
                            }
                        ]
                    },
                ),
                (
                    "extend_existing_test (exact replace of the selected block)",
                    {
                        "patches": [
                            {
                                "path": "tests/plans.spec.ts",
                                "operation": "replace",
                                "start_line": 10,
                                "end_line": 18,
                                "content": "test('opens plan design', async ({ page }) => {\n  await page.goto('/');\n  await page.getByRole('button', { name: 'Plan Design' }).click();\n  await expect(page).toHaveURL(/plan-design/);\n  await expect(page.getByRole('heading', { name: 'Plan Design' })).toBeVisible();\n});",
                                "reason": "Replaces exactly the existing test block lines 10-18, preserving its title and proven steps while adding the heading assertion.",
                            }
                        ]
                    },
                ),
            ],
            "Raw TypeScript outside JSON, markdown fences, a top-level `content` field without `patches`, or an extend patch whose range does not match the selected test block exactly.",
        ),
        "SpecPlacementDecision": (
            {
                "target_spec_file": "tests/plans.spec.ts",
                "create_new": False,
                "confidence": 0.82,
                "decision_trace": {
                    "decision": "extend_existing_spec",
                    "confidence": 0.82,
                    "justification": "Existing spec owns the same route and page object.",
                    "evidence": ["tests/plans.spec.ts covers /plans", "Plan page object exists"],
                    "alternatives": [],
                    "risk": "low",
                    "fallback": "Create tests/generated.spec.ts if ownership changes.",
                    "metadata": {},
                },
            },
            {"target": "tests/plans.spec.ts", "why": "Looks relevant"},
        ),
        "TestActionDecision": (
            {
                "action": "append_new_test",
                "target_test_title": None,
                "confidence": 0.76,
                "decision_trace": {
                    "decision": "append_new_test",
                    "confidence": 0.76,
                    "justification": "Same spec owner, but no existing test proves this behavior.",
                    "evidence": ["Existing spec owns module", "No duplicate title found"],
                    "alternatives": [],
                    "risk": "medium",
                    "fallback": "Create a new generated spec if append is unsafe.",
                    "metadata": {},
                },
            },
            {"decision": "append", "test": "some test"},
        ),
        "SourceIntelligence": (
            {
                "routes": [
                    {
                        "path": "src/app/app.routes.ts",
                        "symbol": "planDesignRoute",
                        "reason": "Declares the /plan-design route",
                    }
                ],
                "components": [
                    {
                        "path": "src/app/plan/plan-tile.component.ts",
                        "symbol": "PlanTileComponent",
                        "reason": "Renders the Plan Design tile",
                    }
                ],
                "services": [],
                "locator_evidence": [
                    {
                        "path": "src/app/plan/plan-tile.component.html",
                        "symbol": "Plan Design",
                        "reason": "Visible button text usable with getByRole",
                    }
                ],
            },
            {"routes": ["/plan-design"], "components": ["PlanTile"]},
        ),
        "CandidateRanking": (
            {
                "ranked": [
                    {
                        "file_path": "tests/plans.spec.ts",
                        "test_title": "opens plan design",
                        "start_line": 10,
                        "relevance": 0.86,
                        "reason": "Covers the same route and page object as the intent",
                    },
                    {
                        "file_path": "tests/orders.spec.ts",
                        "test_title": "creates an order",
                        "start_line": 4,
                        "relevance": 0.15,
                        "reason": "Unrelated module; shares only auth setup",
                    },
                ]
            },
            {"ranked": ["opens plan design", "creates an order"]},
        ),
        "OwnershipResolution": (
            {
                "owner_path": "e2e/pages/plan-page.ts",
                "owner_kind": "page_object",
                "create_new": False,
                "artifacts": ["openDesigner() method", "designerBadge locator"],
                "confidence": 0.78,
                "reason": "PlanPage already owns the plan design screen the needed locators belong to.",
                "decision_trace": {
                    "decision": "reuse_existing_page_object",
                    "confidence": 0.78,
                    "justification": "Existing PlanPage covers the target screen.",
                    "evidence": ["e2e/pages/plan-page.ts owns /plan-design interactions"],
                    "alternatives": [
                        {
                            "decision": "create_new_page_object",
                            "reason_rejected": "Would duplicate PlanPage ownership",
                        }
                    ],
                    "risk": "low",
                    "fallback": "Create a new page object only if PlanPage does not cover the screen.",
                    "metadata": {},
                },
            },
            {},
        ),
        "FlowMergePlan": (
            {
                "stable_region": "login, navigate to /plans, open the plan design tile",
                "extension_region": "assert the designer badge after saving",
                "preserved_steps": [
                    "await page.goto('/plans');",
                    "await page.getByRole('button', { name: 'Plan Design' }).click();",
                ],
                "added_steps": [
                    "await expect(page.getByText('Saved')).toBeVisible();"
                ],
                "confidence": 0.72,
                "decision_trace": {
                    "decision": "extend_after_proven_navigation",
                    "confidence": 0.72,
                    "justification": "Existing flow already proves navigation; only the save assertion is missing.",
                    "evidence": ["preserved_steps exist verbatim in the current test block"],
                    "alternatives": [],
                    "risk": "low",
                    "fallback": "Append a new test if the stable region cannot be preserved.",
                    "metadata": {},
                },
            },
            {"preserved_steps": "keep everything before the assertion"},
        ),
        "LocatorDecisionSet": (
            {
                "decisions": [
                    {
                        "locator": "page.getByRole('button', { name: 'Plan Design' })",
                        "source_evidence": ["src/app/plan/plan-tile.component.html:12"],
                        "alternatives_rejected": ["css=.plan-tile > button"],
                        "confidence": 0.85,
                        "reason": "Accessible role and name grounded in the component template",
                    }
                ]
            },
            {"decisions": ["getByRole('button')"]},
        ),
    }
    if model_name not in examples:
        # No fabricated example: an empty-object "valid example" teaches the model
        # to return output that fails validation. Schema-only guidance instead.
        return (
            "No canonical example is available for this schema. Follow the JSON "
            "schema exactly; populate every required field.\n"
        )
    valid, invalid = examples[model_name]
    if isinstance(valid, list):
        valid_text = "\n\n".join(
            f"Valid response example ({label}):\n{json.dumps(example, indent=2)}"
            for label, example in valid
        )
    else:
        valid_text = f"Valid response example:\n{json.dumps(valid, indent=2)}"
    return (
        f"{valid_text}\n\n"
        "Invalid response example:\n"
        f"{json.dumps(invalid, indent=2)}\n"
    )
