from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.execution_target import ExecutionTarget


class GenerateApiTestCodeRequest(BaseModel):
    user_story_hierarchy_id: int
    api_scenario_id: str
    scenario_name: str
    scenario_steps: list[str] = Field(default_factory=list)
    tenant_id: int | str | None = 1
    repo_path: str
    story_id: str | None = None
    method: str | None = None
    endpoint: str | None = None
    service_name: str | None = None
    execution_target: ExecutionTarget = ExecutionTarget.CI
    assertions: list[str] = Field(default_factory=list)
    branch: str | None = None
    run_validation: bool = True
    additional_context: str | None = None


class GenerateApiTestsRequest(BaseModel):
    """ScriptGen-style request for direct API test generation from a testcase."""

    user_story_hierarchy_id: int
    testcase_id: str
    tenant_id: int | str | None = 1
    testcase_steps: list[str] = Field(default_factory=list)
    setup_steps: list[str] = Field(default_factory=list)
    repo_path: str
    service_name: str | None = None
    target_env: ExecutionTarget = ExecutionTarget.CI
    test_type: str | None = "integration"
    additional_context: str | None = None
    user_story_id: str | None = None
    row_id: int | str | None = None
    testcase_name: str | None = None
    branch: str | None = None
    run_validation: bool = True

    def to_code_request(self) -> GenerateApiTestCodeRequest:
        scenario_name = self.testcase_name or f"{self.user_story_id or 'story'}_{self.testcase_id}"
        return GenerateApiTestCodeRequest(
            user_story_hierarchy_id=self.user_story_hierarchy_id,
            api_scenario_id=self.testcase_id,
            scenario_name=scenario_name,
            scenario_steps=[*self.setup_steps, *self.testcase_steps],
            tenant_id=self.tenant_id,
            repo_path=self.repo_path,
            story_id=self.user_story_id,
            service_name=self.service_name,
            execution_target=self.target_env,
            branch=self.branch,
            run_validation=self.run_validation,
            additional_context=self.additional_context,
        )
