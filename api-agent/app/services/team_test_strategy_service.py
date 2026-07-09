from __future__ import annotations

from pathlib import Path

from app.schemas.repo_profile import RepoProfile, TeamTestStrategyProfile
from app.tools.command_discovery_tool import CommandDiscoveryTool
from app.tools.fixture_scanner_tool import FixtureScannerTool
from app.tools.openapi_scanner_tool import OpenApiScannerTool
from app.tools.path_safety import resolve_workspace_path


class TeamTestStrategyService:
    def __init__(self) -> None:
        self.fixture_scanner = FixtureScannerTool()
        self.command_discovery = CommandDiscoveryTool()
        self.schema_scanner = OpenApiScannerTool()

    def discover(self, repo_path: str, profile: RepoProfile) -> TeamTestStrategyProfile:
        root = resolve_workspace_path(repo_path)
        fixtures = self.fixture_scanner.scan(repo_path)
        commands = self.command_discovery.discover(repo_path)
        schemas = self.schema_scanner.scan(repo_path)

        strategy = TeamTestStrategyProfile(
            primary_language=self._primary_language(profile.languages),
            languages=profile.languages,
            service_frameworks=self._service_frameworks(root, profile.languages),
            build_tools=self._build_tools(profile),
            package_managers=self._package_managers(profile),
            api_styles=self._api_styles(schemas),
            test_frameworks=self._test_frameworks(root, profile),
            mocking_frameworks=self._mocking_frameworks(root),
            contract_tools=self._contract_tools(schemas),
            auth_strategy=self._auth_strategy(fixtures),
            api_test_locations=self._test_locations(profile, target="ci"),
            stage_test_locations=self._test_locations(profile, target="stage"),
            naming_conventions=self._naming_conventions(profile),
            client_patterns=self._client_patterns(root, profile),
            auth_helpers=fixtures["auth_helpers"],
            base_test_classes=fixtures["base_test_classes"],
            fixture_files=fixtures["fixture_files"],
            test_data_builders=fixtures["test_data_builders"],
            api_client_helpers=fixtures["api_client_helpers"],
            existing_ci_test_examples=self._examples(profile, target="ci"),
            existing_stage_test_examples=self._examples(profile, target="stage"),
            endpoint_files=list(dict.fromkeys(endpoint.source_file for endpoint in profile.endpoints))[:50],
            openapi_files=schemas["openapi_files"],
            graphql_schema_files=schemas["graphql_schema_files"],
            ci_command=commands["ci_command"] if isinstance(commands["ci_command"], str) else None,
            stage_command=commands["stage_command"] if isinstance(commands["stage_command"], str) else None,
            validation_commands=list(commands["validation_commands"] or []),
        )
        strategy.confidence = self._confidence(strategy)
        strategy.reasons = self._reasons(strategy)
        strategy.warnings = self._warnings(strategy)
        return strategy

    def _primary_language(self, languages: list[str]) -> str | None:
        for language in ("java", "python", "kotlin", "typescript", "javascript"):
            if language in languages:
                return language
        return languages[0] if languages else None

    def _build_tools(self, profile: RepoProfile) -> list[str]:
        return [profile.build_tool] if profile.build_tool else []

    def _package_managers(self, profile: RepoProfile) -> list[str]:
        return [profile.package_manager] if profile.package_manager else []

    def _service_frameworks(self, root: Path, languages: list[str]) -> list[str]:
        frameworks: list[str] = []
        if "java" in languages:
            if self._contains(root, "org.springframework.boot") or self._contains(root, "@SpringBootApplication"):
                frameworks.append("spring_boot")
        if "python" in languages:
            if self._contains(root, "FastAPI("):
                frameworks.append("fastapi")
            if self._contains(root, "Flask("):
                frameworks.append("flask")
            if (root / "manage.py").exists():
                frameworks.append("django")
        return list(dict.fromkeys(frameworks))

    def _api_styles(self, schemas: dict[str, list[str]]) -> list[str]:
        styles = ["rest"]
        if schemas["openapi_files"]:
            styles.append("openapi")
        if schemas["graphql_schema_files"]:
            styles.append("graphql")
        return styles

    def _test_frameworks(self, root: Path, profile: RepoProfile) -> list[str]:
        frameworks = {test.framework for test in profile.existing_tests if test.framework}
        if "java" in profile.languages:
            if self._contains(root, "org.junit.jupiter"):
                frameworks.add("junit5")
            if self._contains(root, "RestAssured") or self._contains(root, "io.restassured"):
                frameworks.add("rest_assured")
            if self._contains(root, "MockMvc"):
                frameworks.add("mockmvc")
        if "python" in profile.languages:
            if (root / "pytest.ini").exists() or self._contains(root, "pytest"):
                frameworks.add("pytest")
            if self._contains(root, "TestClient"):
                frameworks.add("framework_testclient")
            if self._contains(root, "httpx"):
                frameworks.add("httpx")
            if self._contains(root, "requests"):
                frameworks.add("requests")
        return sorted(frameworks)

    def _mocking_frameworks(self, root: Path) -> list[str]:
        frameworks: list[str] = []
        signals = {
            "mockito": "Mockito",
            "wiremock": "WireMock",
            "responses": "responses",
            "respx": "respx",
            "pytest-mock": "mocker",
            "unittest.mock": "unittest.mock",
        }
        for framework, signal in signals.items():
            if self._contains(root, signal):
                frameworks.append(framework)
        return frameworks

    def _contract_tools(self, schemas: dict[str, list[str]]) -> list[str]:
        tools: list[str] = []
        if schemas["openapi_files"]:
            tools.append("openapi")
        if schemas["graphql_schema_files"]:
            tools.append("graphql")
        return tools

    def _auth_strategy(self, fixtures: dict[str, list[str]]) -> str | None:
        joined = " ".join(fixtures["auth_helpers"]).lower()
        if "jwt" in joined or "token" in joined:
            return "jwt"
        if "auth" in joined:
            return "custom_auth_helper"
        return None

    def _test_locations(self, profile: RepoProfile, target: str) -> list[str]:
        locations: list[str] = []
        for test in profile.existing_tests:
            if test.target != target or "/" not in test.path:
                continue
            locations.append(test.path.rsplit("/", 1)[0])
        if locations:
            return list(dict.fromkeys(locations))[:10]
        if target == "stage":
            if "java" in profile.languages:
                return ["src/integrationTest/java"]
            if "python" in profile.languages:
                return ["tests/stage"]
        if "java" in profile.languages:
            return ["src/test/java"]
        if "python" in profile.languages:
            return ["tests/api", "tests"]
        return []

    def _naming_conventions(self, profile: RepoProfile) -> list[str]:
        conventions: list[str] = []
        if "java" in profile.languages:
            conventions.extend(["<Feature>ControllerTest", "<Feature>IT"])
        if "python" in profile.languages:
            conventions.append("test_<feature>_<behavior>.py")
        return conventions

    def _client_patterns(self, root: Path, profile: RepoProfile) -> list[str]:
        patterns: list[str] = []
        if self._contains(root, "MockMvc"):
            patterns.append("MockMvc for controller/API-slice CI tests")
        if self._contains(root, "RestAssured") or self._contains(root, "io.restassured"):
            patterns.append("RestAssured for integration or stage tests")
        if self._contains(root, "TestClient"):
            patterns.append("framework TestClient fixture")
        if self._contains(root, "httpx"):
            patterns.append("httpx client")
        if self._contains(root, "requests"):
            patterns.append("requests client")
        return patterns

    def _examples(self, profile: RepoProfile, target: str) -> list[str]:
        examples = [test.path for test in profile.existing_tests if test.target == target]
        return examples[:8]

    def _confidence(self, strategy: TeamTestStrategyProfile) -> str:
        score = 0
        score += 1 if strategy.primary_language else 0
        score += 1 if strategy.service_frameworks else 0
        score += 1 if strategy.test_frameworks else 0
        score += 1 if strategy.api_test_locations else 0
        score += 1 if strategy.existing_ci_test_examples or strategy.existing_stage_test_examples else 0
        if score >= 4:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _reasons(self, strategy: TeamTestStrategyProfile) -> list[str]:
        reasons: list[str] = []
        if strategy.primary_language:
            reasons.append(f"Primary language detected: {strategy.primary_language}.")
        if strategy.service_frameworks:
            reasons.append(f"Service frameworks detected: {', '.join(strategy.service_frameworks)}.")
        if strategy.test_frameworks:
            reasons.append(f"Test frameworks detected: {', '.join(strategy.test_frameworks)}.")
        if strategy.api_test_locations:
            reasons.append(f"API test locations detected: {', '.join(strategy.api_test_locations[:3])}.")
        return reasons

    def _warnings(self, strategy: TeamTestStrategyProfile) -> list[str]:
        warnings: list[str] = []
        if not strategy.test_frameworks:
            warnings.append("No existing API test framework was confidently detected.")
        if not strategy.fixture_files:
            warnings.append("No fixture files were confidently detected.")
        if not strategy.ci_command:
            warnings.append("No CI validation command was confidently detected.")
        return warnings

    def _contains(self, root: Path, needle: str) -> bool:
        lower_needle = needle.lower()
        suffixes = {".java", ".kt", ".py", ".txt", ".xml", ".gradle", ".kts", ".toml", ".cfg", ".ini"}
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes or self._skip(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:40000].lower()
            except Exception:
                continue
            if lower_needle in text:
                return True
        return False

    def _skip(self, path: Path) -> bool:
        skipped = {".git", "node_modules", "target", "build", "dist", ".venv", "__pycache__"}
        return any(part in skipped for part in path.parts)
