from __future__ import annotations

from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext


def build_test_placement_prompt(
    output: TestCodeOutput,
    profile: RepoProfile,
    source_context: GenerationSourceContext | None = None,
    repo_understanding=None,
) -> str:
    """Prompt for deciding whether generated tests should extend existing files.

    Mirrors worktop.test_agent spec placement: teams dislike one-file-per-
    scenario sprawl, so when an existing test file already covers the same
    endpoint/service the new tests belong inside it — without touching the
    tests that are already there.
    """
    existing = "\n".join(
        f"- {test.path}" for test in profile.existing_tests[:40]
    ) or "(no existing tests detected)"
    examples = ""
    if source_context and source_context.existing_test_examples:
        examples = "\n\nClosest existing test examples (path + excerpt):\n" + "\n\n".join(
            f"### {example.path}\n{example.content[:2000]}"
            for example in source_context.existing_test_examples[:3]
        )
    conventions = ""
    if repo_understanding is not None:
        conventions = (
            "\n\nDiscovered repository conventions:\n"
            + "\n".join(f"- {item}" for item in repo_understanding.conventions[:10])
        )
    generated = "\n\n".join(
        f"### {file.relative_path} (target={file.test_target})\n{file.content}"
        for file in output.files
    )
    return (
        "You are the test placement agent for API test generation. For each "
        "generated test file below, decide whether it should be written as a "
        "new file (create_new) or merged into an existing test file that "
        "already covers the same endpoint, service, or feature "
        "(extend_existing).\n\n"
        "Rules:\n"
        "1. Prefer extend_existing when an existing test file clearly covers "
        "the same endpoint or service and uses the same framework; otherwise "
        "choose create_new.\n"
        "2. For extend_existing you MUST return merged_content: the complete "
        "target file with every existing test preserved byte-for-byte and the "
        "new tests added in the file's own style (imports deduplicated, "
        "helpers reused).\n"
        "3. Never remove, rename, weaken, or reorder existing tests or "
        "assertions.\n"
        "4. Read the target file first (read_file) before returning "
        "merged_content — never merge from memory.\n"
        "5. When unsure, choose create_new with low confidence.\n\n"
        f"Existing test files in the repository:\n{existing}"
        f"{examples}{conventions}\n\n"
        f"Generated test files to place:\n{generated}"
    )
