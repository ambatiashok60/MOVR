from __future__ import annotations

from app.schemas.repo_profile import RepoProfile
from app.schemas.mock_stub_plan import MockStubPlan
from app.schemas.source_context import GenerationSourceContext


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
