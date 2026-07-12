from __future__ import annotations

import re

from worktop.api_agent.app.schemas.source_context import DependencyCandidate, SourceSnippet


class DependencyScannerTool:
    JAVA_FIELD_PATTERN = re.compile(
        r"(?:private|protected|final|\s)+\s*([A-Z][A-Za-z0-9_<>]+)\s+([a-z][A-Za-z0-9_]*)\s*;"
    )
    PYTHON_DEPENDS_PATTERN = re.compile(r"([a-zA-Z_][A-Za-z0-9_]*)\s*:\s*[^=]+Depends\(")
    JAVA_CONSTRUCTOR_PATTERN = re.compile(
        r"(?:public\s+)?[A-Z][A-Za-z0-9_]*\s*\(([^)]*)\)"
    )
    JAVA_ANNOTATION_PATTERN = re.compile(
        r"@(Autowired|Inject|Resource)\s+(?:private\s+)?([A-Z][A-Za-z0-9_<>]+)\s+([a-z][A-Za-z0-9_]*)"
    )

    def scan(self, endpoint_sources: list[SourceSnippet]) -> list[DependencyCandidate]:
        dependencies: list[DependencyCandidate] = []
        for source in endpoint_sources:
            if source.path.endswith((".java", ".kt")):
                dependencies.extend(self._java_dependencies(source))
            elif source.path.endswith(".py"):
                dependencies.extend(self._python_dependencies(source))
        return self._dedupe(dependencies)

    def _java_dependencies(self, source: SourceSnippet) -> list[DependencyCandidate]:
        deps: list[DependencyCandidate] = []
        for type_name, name in self.JAVA_FIELD_PATTERN.findall(source.content):
            if type_name in {"String", "Integer", "Long", "Boolean", "Object"}:
                continue
            if any(signal in type_name.lower() for signal in ("service", "client", "repository", "gateway")):
                deps.append(
                    DependencyCandidate(
                        name=name,
                        type_name=type_name,
                        source_file=source.path,
                        dependency_kind=self._kind(type_name),
                        reason="Controller/service dependency field detected.",
                    )
                )
        for _, type_name, name in self.JAVA_ANNOTATION_PATTERN.findall(source.content):
            deps.append(DependencyCandidate(
                name=name, type_name=type_name, source_file=source.path,
                dependency_kind=self._kind(type_name),
                reason="Runtime injection annotation detected.",
            ))
        for parameters in self.JAVA_CONSTRUCTOR_PATTERN.findall(source.content):
            for type_name, name in re.findall(r"([A-Z][A-Za-z0-9_<>]+)\s+([a-z][A-Za-z0-9_]*)", parameters):
                if any(signal in type_name.lower() for signal in (
                    "service", "client", "repository", "gateway", "producer", "template"
                )):
                    deps.append(DependencyCandidate(
                        name=name, type_name=type_name, source_file=source.path,
                        dependency_kind=self._kind(type_name),
                        reason="Constructor-injected runtime dependency detected.",
                    ))
        return deps

    def _python_dependencies(self, source: SourceSnippet) -> list[DependencyCandidate]:
        deps: list[DependencyCandidate] = []
        for name in self.PYTHON_DEPENDS_PATTERN.findall(source.content):
            deps.append(
                DependencyCandidate(
                    name=name,
                    type_name=None,
                    source_file=source.path,
                    dependency_kind="fastapi_dependency",
                    reason="FastAPI Depends dependency detected.",
                )
            )
        for signal in ("httpx.", "requests.", "aiohttp."):
            if signal in source.content:
                deps.append(
                    DependencyCandidate(
                        name=signal.rstrip("."),
                        type_name=signal.rstrip("."),
                        source_file=source.path,
                        dependency_kind="http_client",
                        reason="Outbound HTTP client usage detected.",
                    )
                )
        runtime_signals = {
            "KafkaProducer": "message_broker", "KafkaTemplate": "message_broker",
            "boto3.": "cloud_service", "hvac.": "secret_store",
            "os.getenv(": "dynamic_configuration", "import_module(": "dynamic_runtime",
        }
        for signal, kind in runtime_signals.items():
            if signal in source.content:
                deps.append(DependencyCandidate(
                    name=signal.rstrip(".("), type_name=None, source_file=source.path,
                    dependency_kind=kind,
                    reason=f"Runtime dependency signal `{signal}` detected.",
                ))
        return deps

    def _kind(self, type_name: str) -> str:
        lowered = type_name.lower()
        if "client" in lowered or "gateway" in lowered:
            return "downstream_client"
        if "repository" in lowered:
            return "repository"
        if "service" in lowered:
            return "service"
        if any(signal in lowered for signal in ("kafka", "producer", "template")):
            return "message_broker"
        return "unknown"

    def _dedupe(self, dependencies: list[DependencyCandidate]) -> list[DependencyCandidate]:
        seen: set[tuple[str, str | None, str]] = set()
        unique: list[DependencyCandidate] = []
        for dep in dependencies:
            key = (dep.name, dep.type_name, dep.source_file)
            if key in seen:
                continue
            seen.add(key)
            unique.append(dep)
        return unique[:30]
