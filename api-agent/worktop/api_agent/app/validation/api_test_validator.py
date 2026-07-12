from __future__ import annotations

from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.validation_result import ValidationResult
from worktop.api_agent.app.tools.path_safety import resolve_workspace_path
from worktop.api_agent.app.validation.repo_command_validator import RepoCommandValidator


class ApiTestValidator:
    def __init__(self) -> None:
        self.command_validator = RepoCommandValidator()

    def validate(
        self,
        repo_path: str,
        generated_files: list[GeneratedFile],
        profile: RepoProfile | None = None,
        target: str = "ci",
        execute: bool = False,
    ) -> ValidationResult:
        root = resolve_workspace_path(repo_path)
        missing = [file.path for file in generated_files if not (root / file.path).exists()]
        if missing:
            return ValidationResult(
                passed=False,
                summary="Generated file validation failed",
                details=[f"Missing file: {path}" for path in missing],
            )
        reactive_findings: list[str] = []
        if profile is not None and profile.generation_plan and profile.generation_plan.inbound_driver == "webtestclient":
            contents = [(root / file.path).read_text(encoding="utf-8", errors="ignore") for file in generated_files]
            if contents and not any("WebTestClient" in content for content in contents):
                reactive_findings.append("Selected WebTestClient strategy but generated files do not use WebTestClient.")
            if any("Thread.sleep(" in content for content in contents):
                reactive_findings.append("Reactive tests must not use Thread.sleep; use deterministic reactive assertions/time control.")
            if reactive_findings:
                return ValidationResult(passed=False, summary="Reactive API test validation failed", details=reactive_findings)
        graphql_findings: list[str] = []
        if profile is not None and profile.generation_plan and "graphql_tester" in (profile.generation_plan.selected_strategy or ""):
            contents = [(root / file.path).read_text(encoding="utf-8", errors="ignore") for file in generated_files]
            if contents and not any("GraphQlTester" in content for content in contents):
                graphql_findings.append("Selected Spring GraphQL strategy but generated files do not use a GraphQlTester driver.")
            if contents and not any(".document(" in content or ".documentName(" in content for content in contents):
                graphql_findings.append("GraphQL tests must execute an operation document or named document.")
            if contents and not any(".path(" in content or ".errors()" in content for content in contents):
                graphql_findings.append("GraphQL tests must assert response data paths or GraphQL errors.")
            if any("MockMvc" in content or "RestAssured" in content for content in contents):
                graphql_findings.append("GraphQL strategy cannot fall back to REST-only MockMvc/RestAssured calls.")
            if graphql_findings:
                return ValidationResult(passed=False, summary="GraphQL API test validation failed", details=graphql_findings)
        grpc_findings: list[str] = []
        if profile is not None and profile.generation_plan and profile.generation_plan.selected_strategy == "java_grpc_in_process":
            contents = [(root / file.path).read_text(encoding="utf-8", errors="ignore") for file in generated_files]
            if contents and not any("InProcessServerBuilder" in content for content in contents):
                grpc_findings.append("gRPC in-process strategy requires InProcessServerBuilder.")
            if contents and not any("InProcessChannelBuilder" in content for content in contents):
                grpc_findings.append("gRPC in-process strategy requires InProcessChannelBuilder.")
            if contents and not any(token in content for content in contents for token in ("GrpcCleanupRule", "shutdownNow()", "shutdown()")):
                grpc_findings.append("gRPC tests must clean up both server and channel resources.")
            if contents and not any(token in content for content in contents for token in ("assertThat", "assertEquals", "StatusRuntimeException", "Status.Code")):
                grpc_findings.append("gRPC tests must assert a protobuf response or gRPC status.")
            if any("RestAssured" in content or "MockMvc" in content for content in contents):
                grpc_findings.append("gRPC strategy cannot use REST-only MockMvc/RestAssured drivers.")
            if grpc_findings:
                return ValidationResult(passed=False, summary="gRPC API test validation failed", details=grpc_findings)
        if profile is not None:
            command_result = self.command_validator.validate(
                profile,
                generated_files,
                target=target,
                execute=execute,
            )
            command_result.details = [
                "Generated file existence check passed.",
                *command_result.details,
            ]
            return command_result
        return ValidationResult(
            passed=True,
            summary="Generated files were written successfully",
            details=[f"Found {file.path}" for file in generated_files],
        )
