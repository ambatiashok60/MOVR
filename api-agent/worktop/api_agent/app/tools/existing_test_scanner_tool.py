from __future__ import annotations

from worktop.api_agent.app.schemas.repo_profile import ExistingApiTestCandidate
from worktop.api_agent.app.tools.file_reader_tool import FileReaderTool


class ExistingTestScannerTool:
    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def scan(self, repo_path: str, max_tests: int = 120) -> list[ExistingApiTestCandidate]:
        suffixes = (".java", ".kt", ".ts", ".js", ".py", ".go", ".cs")
        tests: list[ExistingApiTestCandidate] = []
        for relative in self.reader.list_files(repo_path, suffixes=suffixes, max_files=1500):
            lower = relative.lower()
            if not self._looks_like_api_test(lower):
                continue
            text = self.reader.read_text(repo_path, relative, max_chars=12000)
            framework, signals = self._framework_and_signals(lower, text)
            tests.append(
                ExistingApiTestCandidate(
                    path=relative,
                    framework=framework,
                    target=self._target(lower),
                    strategy=self._strategy(lower, text),
                    signals=signals,
                )
            )
            if len(tests) >= max_tests:
                break
        return tests

    def _looks_like_api_test(self, path: str) -> bool:
        test_signal = any(signal in path for signal in ("test", "spec", "it."))
        api_signal = any(signal in path for signal in ("api", "controller", "resource", "client", "contract"))
        return test_signal and api_signal

    def _framework(self, path: str) -> str | None:
        if path.endswith((".java", ".kt")):
            return "junit"
        if path.endswith((".ts", ".js")):
            return "jest_or_playwright"
        if path.endswith(".py"):
            return "pytest"
        return None

    def _framework_and_signals(self, path: str, text: str) -> tuple[str | None, list[str]]:
        lowered = text.lower()
        signals: list[str] = []
        framework = self._framework(path)
        if "restassured" in lowered or "io.restassured" in lowered:
            framework = "rest_assured"
            signals.append("rest_assured")
        if "mockmvc" in lowered:
            framework = "mockmvc"
            signals.append("mockmvc")
        if "org.junit.jupiter" in lowered:
            framework = framework or "junit5"
            signals.append("junit5")
        if "testclient" in lowered:
            framework = "framework_testclient"
            signals.append("testclient")
        if "httpx" in lowered:
            framework = "httpx"
            signals.append("httpx")
        if "requests" in lowered:
            framework = "requests"
            signals.append("requests")
        if "pytest" in lowered or path.endswith(".py"):
            framework = framework or "pytest"
            signals.append("pytest")
        if "wiremock" in lowered:
            signals.append("wiremock")
        if "mockito" in lowered:
            signals.append("mockito")
        if "respx" in lowered:
            signals.append("respx")
        return framework, list(dict.fromkeys(signals))

    def _target(self, path: str) -> str:
        if any(signal in path for signal in ("stage", "integration", "it.", "e2e")):
            return "stage"
        return "ci"

    def _strategy(self, path: str, text: str) -> str | None:
        lowered = f"{path}\n{text}".lower()
        if "contract" in lowered or "openapi" in lowered or "schema" in lowered:
            return "contract/schema"
        if "mockmvc" in lowered or "controller" in lowered:
            return "controller/api-slice"
        if "restassured" in lowered or "integration" in lowered or "it." in lowered:
            return "integration"
        if "stage" in lowered:
            return "stage smoke"
        if "auth" in lowered or "security" in lowered:
            return "auth/security"
        return None
