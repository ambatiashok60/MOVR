from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.repository_policy import RepositoryPolicy
from worktop.test_agent.app.schemas.validation_result import ValidationCheck
from worktop.core_services.app.utility.custom_logger.logging import logger


_POLICY_CANDIDATES = (
    ".movr/test-agent-policy.yaml",
    ".movr/test-agent-policy.yml",
    ".movr/test-agent-policy.json",
    "test-agent-policy.yaml",
    "test-agent-policy.yml",
    "test-agent-policy.json",
)
_SPEC_SUFFIXES = (".spec.ts", ".spec.tsx", ".e2e.ts", ".e2e.tsx", ".pw.ts", ".playwright.ts")
_INLINE_LOCATOR_PATTERN = re.compile(
    r"page\.(?:locator|getByTestId|getByRole|getByText|getByLabel|getByPlaceholder)\s*\("
)


class RepositoryPolicyService:
    """Load and enforce per-repository generation policy.

    Different repositories have different rules (where assertions live, who
    owns locators, whether hooks may be touched). The policy file is read from
    the target repository so the same engine adapts per repo instead of
    hard-coding one team's conventions.
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
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'repository_policy', 'loaded', {'source': candidate, 'generation': policy.generation.model_dump()})
                return policy
            except Exception as exc:
                logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'repository_policy', 'invalid_policy_file', {'source': candidate, 'error': exc})
                break
        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'repository_policy', 'defaults_applied', {})
        return RepositoryPolicy()

    def checks(self, patches: PatchSet, policy: RepositoryPolicy) -> list[ValidationCheck]:
        generation = policy.generation
        return [
            self._before_each_check(patches, generation.allow_before_each_updates),
            self._assertion_location_check(patches, generation.assertion_location),
            self._locator_owner_check(patches, generation.locator_owner),
            self._require_describe_check(patches, generation.require_describe),
        ]

    def _before_each_check(self, patches: PatchSet, allowed: bool) -> ValidationCheck:
        if allowed:
            return ValidationCheck(
                name="policy_before_each",
                passed=True,
                output="Policy allows beforeEach updates.",
            )
        findings = [
            f"{patch.path}: policy forbids modifying beforeEach hooks in existing files"
            for patch in patches.patches
            if patch.operation != "create" and "beforeEach(" in patch.content
        ]
        return ValidationCheck(
            name="policy_before_each",
            passed=not findings,
            output="\n".join(findings) or "No beforeEach modifications in existing files.",
        )

    def _assertion_location_check(
        self, patches: PatchSet, location: str
    ) -> ValidationCheck:
        findings: list[str] = []
        if location == "spec":
            findings = [
                f"{patch.path}: policy requires assertions only in spec files"
                for patch in patches.patches
                if patch.path.endswith((".ts", ".tsx"))
                and not patch.path.endswith(_SPEC_SUFFIXES)
                and "expect(" in patch.content
            ]
        elif location == "page_object":
            findings = [
                f"{patch.path}: policy requires assertions inside page objects, not specs"
                for patch in patches.patches
                if patch.path.endswith(_SPEC_SUFFIXES) and "expect(" in patch.content
            ]
        return ValidationCheck(
            name="policy_assertion_location",
            passed=not findings,
            output="\n".join(findings)
            or f"Assertion placement conforms to policy ({location}).",
        )

    def _locator_owner_check(self, patches: PatchSet, owner: str) -> ValidationCheck:
        findings: list[str] = []
        if owner == "page_object":
            findings = [
                f"{patch.path}: policy assigns locators to page objects; "
                "inline page locators are not allowed in specs"
                for patch in patches.patches
                if patch.path.endswith(_SPEC_SUFFIXES)
                and _INLINE_LOCATOR_PATTERN.search(patch.content)
            ]
        return ValidationCheck(
            name="policy_locator_owner",
            passed=not findings,
            output="\n".join(findings) or f"Locator ownership conforms to policy ({owner}).",
        )

    def _require_describe_check(
        self, patches: PatchSet, required: bool
    ) -> ValidationCheck:
        if not required:
            return ValidationCheck(
                name="policy_require_describe",
                passed=True,
                output="Policy does not require describe blocks.",
            )
        findings = [
            f"{patch.path}: policy requires a test.describe() block in created specs"
            for patch in patches.patches
            if patch.operation == "create"
            and patch.path.endswith(_SPEC_SUFFIXES)
            and "describe(" not in patch.content
        ]
        return ValidationCheck(
            name="policy_require_describe",
            passed=not findings,
            output="\n".join(findings) or "Created specs declare describe blocks.",
        )

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

        Supports two-level nesting of `key:` blocks with scalar `key: value`
        entries and `#` comments — exactly the shape of the policy file — so a
        repository policy works without a YAML dependency installed.
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
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value.strip("'\"")
