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
    examples: dict[str, tuple[dict[str, Any], Any]] = {
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
            {
                "patches": [
                    {
                        "path": "tests/generated.spec.ts",
                        "operation": "create",
                        "start_line": None,
                        "end_line": None,
                        "content": "import { test, expect } from '@playwright/test';\n\ntest('opens plan design', async ({ page }) => {\n  await page.goto('/');\n  await page.getByRole('button', { name: 'Plan Design' }).click();\n  await expect(page).toHaveURL(/plan-design/);\n});\n",
                        "reason": "Creates Playwright coverage for the requested navigation flow.",
                    }
                ]
            },
            "Raw TypeScript outside JSON, markdown fences, or a top-level `content` field without `patches`.",
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
    }
    valid, invalid = examples.get(model_name, ({}, "Any response that does not validate against the schema."))
    return (
        "Valid response example:\n"
        f"{json.dumps(valid, indent=2)}\n\n"
        "Invalid response example:\n"
        f"{json.dumps(invalid, indent=2)}\n"
    )
