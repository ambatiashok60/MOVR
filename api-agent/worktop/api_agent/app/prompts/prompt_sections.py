from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext


def response_contract(response_model: type[BaseModel]) -> str:
    """Schema-derived response contract with canonical examples.

    Keeps prompts and Pydantic schemas from drifting apart: the JSON schema is
    generated from the model itself, and known models carry a valid/invalid
    example pair so the model never has to guess the shape.
    """
    schema = response_model.model_json_schema()
    examples = _response_examples(response_model.__name__)
    return (
        "Return only valid JSON. Do not include markdown fences or prose.\n"
        "Return exactly one JSON object that validates against this Pydantic "
        f"model: {response_model.__name__}.\n"
        "Use only fields from the schema. Do not invent extra keys. Populate "
        "every required field.\n\n"
        f"{examples}"
        "JSON schema:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _response_examples(model_name: str) -> str:
    examples: dict[str, tuple[Any, Any]] = {
        "ScenarioPlanOutput": (
            {
                "scenarios": [
                    {
                        "api_scenario_id": "create-order-happy-path-ci",
                        "scenario_name": "Create order succeeds with valid payload",
                        "scenario_type": "positive",
                        "service_name": "OrderService",
                        "method": "POST",
                        "endpoint": "/api/orders",
                        "priority": "high",
                        "execution_target": "ci",
                        "reason": "Fast deterministic contract check belongs in PR CI.",
                        "scenario_steps": [
                            "Build a valid order payload from the acceptance criteria.",
                            "POST it to /api/orders through the controller layer.",
                            "Verify the created response contract.",
                        ],
                        "assertions": [
                            "Response status is 201",
                            "Response body contains the new order id",
                        ],
                    }
                ],
                "warnings": [],
            },
            {
                "scenarios": [
                    {
                        "scenario_name": "some test",
                        "scenario_type": "smoke",
                        "method": "post",
                    }
                ]
            },
        ),
        "TestCodeOutput": (
            {
                "files": [
                    {
                        "relative_path": "src/test/java/com/acme/orders/OrderControllerTest.java",
                        "content": "package com.acme.orders;\n\nimport org.junit.jupiter.api.Test;\n// full compiling test file content here\n",
                        "test_target": "ci",
                        "summary": "MockMvc test proving order creation contract",
                    }
                ],
                "summary": "Generated CI MockMvc coverage for order creation",
                "warnings": [],
            },
            {
                "files": [
                    {
                        "relative_path": "src/main/java/com/acme/orders/OrderService.java",
                        "content": "// raw code fragment",
                        "test_target": "pr",
                    }
                ]
            },
        ),
        "StrategyReasoningOutput": (
            {
                "decision": "confirm",
                "selected_strategy": "java_spring_webtestclient",
                "confidence": 0.94,
                "evidence_ids": ["ev-a1b2c3d4"],
                "reasons": ["Existing WebTestClient tests match the reactive Spring source."],
                "rejected_alternatives": [{"strategy_name": "java_spring_mockmvc", "reason": "The endpoint is reactive.", "incompatible_capabilities": ["spring_webflux"]}],
                "unresolved_questions": [],
                "recommended_next_stage": "dependency_planning",
            },
            {"decision": "yes", "selected_strategy": "invented-framework", "confidence": 5, "reasons": []},
        ),
    }
    examples["DiscoveryTurn"] = (
        {
            "requests": [
                {"kind": "read_file", "target": "package.json"},
                {"kind": "search", "target": "supertest"},
                {"kind": "list_dir", "target": "tests"},
            ],
            "understanding": None,
        },
        {"requests": ["read package.json"], "understanding": "looks like node"},
    )
    if model_name not in examples:
        return (
            "No canonical example is available for this schema. Follow the JSON "
            "schema exactly; populate every required field.\n\n"
        )
    valid, invalid = examples[model_name]
    return (
        "Valid response example:\n"
        f"{json.dumps(valid, indent=2)}\n\n"
        "Invalid response example (do not do this):\n"
        f"{json.dumps(invalid, indent=2)}\n\n"
    )


def render_repo_understanding(understanding: Any | None) -> str:
    """Discovered (model-explored) repository understanding for prompts.

    When present this outranks the scanner-derived profile and the generic
    strategy guidance: it is evidence the model itself read from the repo.
    """
    if understanding is None:
        return "Discovered repository understanding: none (fall back to the scanned profile)."
    conventions = "\n".join(f"- {item}" for item in understanding.conventions)
    examples = "\n".join(f"- {item}" for item in understanding.example_test_paths)
    risks = "\n".join(f"- {item}" for item in understanding.risks)
    return f"""
Discovered repository understanding (model-explored evidence; prefer this over
generic strategy guidance when they disagree):
- languages: {', '.join(understanding.languages) or 'unknown'}
- service frameworks: {', '.join(understanding.service_frameworks) or 'unknown'}
- test frameworks: {', '.join(understanding.test_frameworks) or 'unknown'}
- test locations: {', '.join(understanding.test_locations) or 'unknown'}
- CI test command: {understanding.ci_test_command or 'unknown'}
- stage test command: {understanding.stage_test_command or 'unknown'}
- confidence: {understanding.confidence}

Conventions observed:
{conventions or '- none recorded'}

Example tests to imitate:
{examples or '- none recorded'}

Risks:
{risks or '- none'}
""".strip()


def render_repo_profile(profile: RepoProfile) -> str:
    endpoints = "\n".join(
        f"- {endpoint.method} {endpoint.path} in {endpoint.source_file}"
        for endpoint in profile.endpoints[:30]
    )
    tests = "\n".join(
        f"- {test.path} ({test.framework or 'unknown'}, {test.target or 'unknown'})"
        for test in profile.existing_tests[:30]
    )
    findings = "\n".join(f"- {finding}" for finding in profile.findings)
    strategy = profile.team_strategy
    strategy_reasons = "\n".join(f"- {reason}" for reason in strategy.reasons)
    strategy_warnings = "\n".join(f"- {warning}" for warning in strategy.warnings)
    composed = profile.generation_plan
    composed_summary = "- none"
    if composed is not None:
        substitutions = ", ".join(f"{item.dependency_capability}->{item.mechanism}" for item in composed.dependency_substitutions) or "none"
        composed_summary = (
            f"- selected: {composed.selected_strategy or 'unknown'}\n"
            f"- status/confidence: {composed.status}/{composed.confidence}\n"
            f"- bootstrap: {composed.bootstrap or 'unknown'}\n"
            f"- inbound driver: {composed.inbound_driver or 'unknown'}\n"
            f"- dependency substitutions: {substitutions}\n"
            f"- review reasons: {'; '.join(composed.review_reasons) or 'none'}"
        )
    return f"""
Repository:
- path: {profile.repo_path}
- build tool: {profile.build_tool or 'unknown'}
- package manager: {profile.package_manager or 'unknown'}
- languages: {', '.join(profile.languages) or 'unknown'}
- service frameworks: {', '.join(strategy.service_frameworks) or 'unknown'}
- API styles: {', '.join(strategy.api_styles) or 'unknown'}
- test frameworks: {', '.join(strategy.test_frameworks) or 'unknown'}
- mocking frameworks: {', '.join(strategy.mocking_frameworks) or 'unknown'}
- CI command: {strategy.ci_command or 'unknown'}
- stage command: {strategy.stage_command or 'unknown'}
- strategy confidence: {strategy.confidence}

Team conventions:
- API test locations: {', '.join(strategy.api_test_locations) or 'unknown'}
- stage test locations: {', '.join(strategy.stage_test_locations) or 'unknown'}
- naming conventions: {', '.join(strategy.naming_conventions) or 'unknown'}
- client patterns: {', '.join(strategy.client_patterns) or 'unknown'}
- auth helpers: {', '.join(strategy.auth_helpers[:8]) or 'unknown'}
- fixture files: {', '.join(strategy.fixture_files[:8]) or 'unknown'}
- API client helpers: {', '.join(strategy.api_client_helpers[:8]) or 'unknown'}
- CI examples: {', '.join(strategy.existing_ci_test_examples[:8]) or 'none'}
- stage examples: {', '.join(strategy.existing_stage_test_examples[:8]) or 'none'}

Detected endpoints:
{endpoints or '- none detected'}

Existing API tests:
{tests or '- none detected'}

Findings:
{findings or '- none'}

Strategy reasons:
{strategy_reasons or '- none'}

Strategy warnings:
{strategy_warnings or '- none'}

Capability-composed generation plan:
{composed_summary}
""".strip()


def render_source_context(source_context: GenerationSourceContext | None) -> str:
    if source_context is None:
        return "Source context: none"
    endpoint_sources = "\n\n".join(
        f"### {snippet.path}\nReason: {snippet.reason}\n```text\n{snippet.content[:5000]}\n```"
        for snippet in source_context.endpoint_sources[:4]
    )
    examples = "\n\n".join(
        f"### {example.path}\nTarget: {example.target or 'unknown'} | "
        f"Framework: {example.framework or 'unknown'} | Score: {example.relevance_score}\n"
        f"Signals: {', '.join(example.signals) or 'none'}\n"
        f"```text\n{example.content[:6000]}\n```"
        for example in source_context.existing_test_examples[:5]
    )
    fixtures = "\n\n".join(
        f"### {snippet.path}\nReason: {snippet.reason}\n```text\n{snippet.content[:3500]}\n```"
        for snippet in source_context.fixture_snippets[:5]
    )
    warnings = "\n".join(f"- {warning}" for warning in source_context.warnings)
    return f"""
Source context:

Endpoint/controller sources:
{endpoint_sources or '- none'}

Existing test examples to follow:
{examples or '- none'}

Fixture/auth/client helpers to reuse:
{fixtures or '- none'}

Source context warnings:
{warnings or '- none'}
""".strip()


def render_mock_stub_plan(mock_stub_plan: MockStubPlan | None) -> str:
    if mock_stub_plan is None:
        return "Mock/stub plan: none"
    dependencies = "\n".join(
        f"- {dep.name} ({dep.type_name or 'unknown'}, {dep.dependency_kind}) from {dep.source_file}: {dep.reason}"
        for dep in mock_stub_plan.dependencies_to_mock
    )
    stubs = "\n".join(f"- {stub}" for stub in mock_stub_plan.generated_stubs)
    helpers = "\n".join(f"- {helper}" for helper in mock_stub_plan.reused_helpers)
    external = "\n".join(f"- {service}" for service in mock_stub_plan.external_services_to_stub)
    warnings = "\n".join(f"- {warning}" for warning in mock_stub_plan.warnings)
    return f"""
Mock/stub plan:
- strategy: {mock_stub_plan.strategy or 'unknown'}

Dependencies to mock or override:
{dependencies or '- none'}

Helpers to reuse:
{helpers or '- none'}

Generated stub intentions:
{stubs or '- none'}

External services to stub:
{external or '- none'}

Mock/stub warnings:
{warnings or '- none'}
""".strip()
