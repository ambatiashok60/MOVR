from __future__ import annotations

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.repo_profile import RepoProfile
from app.schemas.source_context import ExistingTestExample, GenerationSourceContext, SourceSnippet
from app.tools.file_reader_tool import FileReaderTool


class SourceContextTool:
    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def build(
        self,
        repo_path: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        max_examples: int = 6,
    ) -> GenerationSourceContext:
        endpoint_sources = self._endpoint_sources(repo_path, request, profile)
        examples = self._examples(repo_path, request, profile, max_examples=max_examples)
        fixture_snippets = self._fixture_snippets(repo_path, profile)
        warnings: list[str] = []
        if not examples:
            warnings.append("No close existing API test examples were found.")
        if not endpoint_sources:
            warnings.append("No endpoint/controller source snippets were found.")
        return GenerationSourceContext(
            endpoint_sources=endpoint_sources,
            existing_test_examples=examples,
            fixture_snippets=fixture_snippets,
            warnings=warnings,
        )

    def _endpoint_sources(
        self,
        repo_path: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> list[SourceSnippet]:
        scored: list[tuple[int, str]] = []
        endpoint = (request.endpoint or "").lower()
        service = (request.service_name or "").lower()
        for candidate in profile.endpoints:
            score = 0
            if endpoint and endpoint in candidate.path.lower():
                score += 5
            if request.method and request.method.upper() == candidate.method.upper():
                score += 2
            if service and candidate.service_name and service in candidate.service_name.lower():
                score += 3
            if score:
                scored.append((score, candidate.source_file))
        paths = [path for _, path in sorted(scored, reverse=True)]
        if not paths:
            paths = profile.team_strategy.endpoint_files[:3]
        snippets: list[SourceSnippet] = []
        for path in list(dict.fromkeys(paths))[:5]:
            snippets.append(
                SourceSnippet(
                    path=path,
                    reason="Closest endpoint/controller source for requested scenario.",
                    content=self.reader.read_text(repo_path, path, max_chars=12000),
                )
            )
        return snippets

    def _examples(
        self,
        repo_path: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        max_examples: int,
    ) -> list[ExistingTestExample]:
        scored: list[tuple[int, object]] = []
        terms = self._terms(request)
        for test in profile.existing_tests:
            score = 0
            lower_path = test.path.lower()
            score += 4 if test.target == str(request.execution_target) else 0
            score += 2 if test.framework in profile.team_strategy.test_frameworks else 0
            score += sum(1 for term in terms if term and term in lower_path)
            score += 2 if request.service_name and request.service_name.lower() in lower_path else 0
            scored.append((score, test))
        examples: list[ExistingTestExample] = []
        for score, test in sorted(scored, key=lambda item: item[0], reverse=True)[:max_examples]:
            if score <= 0 and examples:
                continue
            examples.append(
                ExistingTestExample(
                    path=test.path,
                    target=test.target,
                    framework=test.framework,
                    strategy=test.strategy,
                    relevance_score=score,
                    signals=test.signals,
                    content=self.reader.read_text(repo_path, test.path, max_chars=16000),
                )
            )
        return examples

    def _fixture_snippets(self, repo_path: str, profile: RepoProfile) -> list[SourceSnippet]:
        paths = [
            *profile.team_strategy.fixture_files[:4],
            *profile.team_strategy.auth_helpers[:3],
            *profile.team_strategy.api_client_helpers[:3],
        ]
        snippets: list[SourceSnippet] = []
        for path in list(dict.fromkeys(paths))[:8]:
            snippets.append(
                SourceSnippet(
                    path=path,
                    reason="Existing fixture/auth/client helper to reuse.",
                    content=self.reader.read_text(repo_path, path, max_chars=10000),
                )
            )
        return snippets

    def _terms(self, request: GenerateApiTestCodeRequest) -> list[str]:
        raw = " ".join(
            value
            for value in (
                request.scenario_name,
                request.service_name or "",
                request.endpoint or "",
                request.story_id or "",
            )
            if value
        )
        return [
            term.strip("/{}_-").lower()
            for term in raw.replace("/", " ").replace("-", " ").replace("_", " ").split()
            if len(term.strip("/{}_-")) >= 3
        ]
