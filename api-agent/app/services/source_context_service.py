from __future__ import annotations

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.repo_profile import RepoProfile
from app.schemas.source_context import GenerationSourceContext
from app.tools.source_context_tool import SourceContextTool


class SourceContextService:
    def __init__(self) -> None:
        self.tool = SourceContextTool()

    def build(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> GenerationSourceContext:
        return self.tool.build(request.repo_path, request, profile)
