from __future__ import annotations

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.tools.source_context_tool import SourceContextTool


class SourceContextService:
    def __init__(self) -> None:
        self.tool = SourceContextTool()

    def build(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> GenerationSourceContext:
        return self.tool.build(request.repo_path, request, profile)
