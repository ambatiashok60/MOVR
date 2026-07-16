from __future__ import annotations

import json

from worktop.api_agent.app.prompts.prompt_sections import response_contract
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext


def build_critic_review_prompt(
    output: TestCodeOutput,
    request: GenerateApiTestCodeRequest,
    profile: RepoProfile,
    source_context: GenerationSourceContext | None = None,
    mock_stub_plan=None,
    repo_understanding=None,
    validation_failure: str | None = None,
) -> str:
    """Critic pass over generated API tests (test_agent critic_review parity).

    The critic re-reads the generated files against the scenario contract and
    repository evidence and returns the corrected full file set — or the same
    files unchanged when they already hold up.
    """
    endpoints = "\n".join(
        f"- {endpoint.method} {endpoint.path} ({endpoint.source_file})"
        for endpoint in profile.endpoints[:30]
    ) or "(no endpoints detected)"
    examples = ""
    if source_context and source_context.existing_test_examples:
        examples = "\n\nExisting test examples showing repository conventions:\n" + "\n\n".join(
            f"### {example.path}\n{example.content[:1500]}"
            for example in source_context.existing_test_examples[:2]
        )
    mock_plan = ""
    if mock_stub_plan is not None:
        mock_plan = (
            "\n\nMock/stub plan (a promise, not advice):\n"
            f"{json.dumps(mock_stub_plan.model_dump(), indent=2, default=str)[:3000]}"
        )
    conventions = ""
    if repo_understanding is not None:
        conventions = "\n\nDiscovered repository conventions:\n" + "\n".join(
            f"- {item}" for item in repo_understanding.conventions[:10]
        )
    failure = ""
    if validation_failure:
        failure = (
            "\n\nThese files were produced while repairing a failed execution. "
            "The failure being fixed was:\n"
            f"{validation_failure[:4000]}"
        )
    files = "\n\n".join(
        f"### {file.relative_path} (target={file.test_target})\n{file.content}"
        for file in output.files
    )
    return (
        "You are the critic agent reviewing generated API tests for CI "
        "quality before they are written to the repository.\n\n"
        "Rules:\n"
        "1. Every scenario step and assertion below must be genuinely "
        "exercised and asserted — reject shallow assertions that do not "
        "prove the API behavior.\n"
        "2. Tests must only call endpoints that exist in the repository "
        "evidence; never invent endpoints, fields, or status codes.\n"
        "3. CI-target tests must be deterministic and offline: no sleeps, no "
        "real network calls, and every dependency named in the mock/stub "
        "plan must actually be mocked or stubbed.\n"
        "4. Follow the repository's own conventions (fixtures, helpers, base "
        "classes, naming) as shown in the examples.\n"
        "5. Return the COMPLETE corrected file set: keep the same "
        "relative_path and test_target for every file, fix content only "
        "where a rule is violated, and return files unchanged when they "
        "already hold up. Never drop or add files.\n\n"
        f"Scenario: {request.scenario_name}\n"
        "Scenario steps:\n"
        + "\n".join(f"- {step}" for step in request.scenario_steps)
        + (
            "\nRequired assertions:\n"
            + "\n".join(f"- {assertion}" for assertion in request.assertions)
            if request.assertions
            else ""
        )
        + f"\n\nEndpoints detected in the repository:\n{endpoints}"
        f"{examples}{mock_plan}{conventions}{failure}\n\n"
        f"Generated files under review:\n{files}\n\n"
        f"{response_contract(TestCodeOutput)}"
    )
