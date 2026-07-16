from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from worktop.api_agent.app.schemas.api_scenario import ApiScenario
from worktop.api_agent.app.schemas.repository_policy import RepositoryPolicy
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_POLICY_CANDIDATES = (
    ".movr/api-agent-policy.yaml",
    ".movr/api-agent-policy.yml",
    ".movr/api-agent-policy.json",
    "api-agent-policy.yaml",
    "api-agent-policy.yml",
    "api-agent-policy.json",
)
_REAL_NETWORK_PATTERN = re.compile(
    r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\$\{)[\w.-]+"
)


class RepositoryPolicyService:
    """Load and enforce per-repository API generation policy.

    Different repositories have different rules (whether CI tests may touch
    real networks, which frameworks are sanctioned, how many files one
    generation may emit). The policy file lives in the target repository so
    the same engine adapts per repo.
    """

    def load(self, repo_path: str) -> RepositoryPolicy:
        root = Path(repo_path)
        for candidate in _POLICY_CANDIDATES:
            path = root / candidate
            if not path.is_file():
                continue
            try:
                data = self._parse(path)
                policy = RepositoryPolicy.model_validate({**data, "source": candidate})
                logger.info(
                    "Repository policy loaded from %s: %s",
                    candidate,
                    policy.generation.model_dump(),
                )
                return policy
            except Exception as exc:
                logger.warning("Invalid policy file %s (%s); using defaults.", candidate, exc)
                break
        logger.info("No repository policy file found; defaults applied.")
        return RepositoryPolicy()

    def file_findings(
        self,
        policy: RepositoryPolicy,
        files: list[tuple[str, str, str]],
    ) -> list[str]:
        """Policy findings over generated files.

        ``files`` is (path, test_target, content). Findings become review
        reasons — the generation still lands, but never silently.
        """
        generation = policy.generation
        findings: list[str] = []
        if len(files) > generation.max_files_per_generation:
            findings.append(
                f"Policy allows at most {generation.max_files_per_generation} "
                f"file(s) per generation; {len(files)} were generated."
            )
        for path, target, content in files:
            if (
                generation.forbid_real_network_in_ci
                and target in ("ci", "both")
                and (match := _REAL_NETWORK_PATTERN.search(content))
            ):
                findings.append(
                    f"{path}: policy forbids real network calls in CI tests; "
                    f"found `{match.group(0)}`."
                )
            if generation.allowed_test_frameworks and not any(
                framework.lower() in content.lower()
                for framework in generation.allowed_test_frameworks
            ):
                findings.append(
                    f"{path}: policy restricts test frameworks to "
                    f"{generation.allowed_test_frameworks}; none were referenced."
                )
        return findings

    def scenario_findings(
        self,
        policy: RepositoryPolicy,
        scenarios: list[ApiScenario],
    ) -> list[str]:
        findings: list[str] = []
        if (
            policy.generation.require_negative_scenarios
            and scenarios
            and not any(s.scenario_type == "negative" for s in scenarios)
        ):
            findings.append(
                "Policy requires at least one negative scenario; the plan has none."
            )
        return findings

    def _parse(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return json.loads(text)
        try:
            import yaml  # type: ignore[import-not-found]

            return yaml.safe_load(text) or {}
        except ImportError:
            return self._parse_simple_yaml(text)

    def _parse_simple_yaml(self, text: str) -> dict[str, Any]:
        """Minimal YAML-subset parser for the flat policy grammar.

        Supports two-level nesting of `key:` blocks with scalar values and
        `[a, b]` inline lists, so a repository policy works without a YAML
        dependency installed.
        """
        root: dict[str, Any] = {}
        current: dict[str, Any] = root
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indented = line.startswith((" ", "\t"))
            key, _, value = line.strip().partition(":")
            value = value.strip()
            if not indented:
                if value:
                    root[key] = self._coerce_scalar(value)
                    current = root
                else:
                    current = root.setdefault(key, {})
            else:
                current[key] = self._coerce_scalar(value)
        return root

    def _coerce_scalar(self, value: str) -> Any:
        lowered = value.lower()
        if lowered in {"true", "yes", "on"}:
            return True
        if lowered in {"false", "no", "off"}:
            return False
        if lowered in {"null", "~", ""}:
            return None
        if value.startswith("[") and value.endswith("]"):
            return [
                item.strip().strip("'\"")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value.strip("'\"")
