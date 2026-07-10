from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


from app.schemas.repo_profile import RepoProfile
from app.utils.logging_utils import build_log_context

logger = logging.getLogger(__name__)


class RepoStrategyService:
    def detect(self, repo_path: str, branch: str | None = None) -> RepoProfile:
        context = build_log_context(repo_path=repo_path, branch=branch, stage="repo_strategy")
        logger.info(
            "[playwright-generation] stage=repo_strategy status=started repo=%s branch=%s",
            repo_path,
            branch,
        )
        try:
            root = Path(repo_path)
            if not root.exists() or not root.is_dir():
                profile = RepoProfile(
                    repo_path=repo_path,
                    branch=branch,
                    support_status="unsupported",
                    support_blockers=["Repository path does not exist or is not a directory"],
                )
                self._log_profile(profile)
                return profile

            package_json_files = self._find_package_json_files(root)
            package_json = self._load_root_package_json(root)
            package_scripts = self._extract_package_scripts(package_json)
            dependencies = self._collect_dependencies(package_json)
            configs = self._relative_files(root, "playwright.config.*")
            spec_files = self._find_playwright_spec_files(root)
            lockfiles = self._detect_lockfiles(root)
            logger.debug(
                "[playwright-generation] stage=repo_strategy status=discovered "
                "package_json_files=%s configs=%s spec_files=%s lockfiles=%s",
                [str(path.relative_to(root)) for path in package_json_files],
                configs,
                spec_files,
                lockfiles,
            )
            package_manager = self._detect_package_manager(lockfiles)
            frameworks = self._detect_frameworks(dependencies, root)
            monorepo_tooling = self._detect_monorepo_tooling(root, dependencies)
            unsupported_signals = self._detect_unsupported_signals(root, dependencies)
            logger.debug(
                "[playwright-generation] stage=repo_strategy status=classified "
                "package_manager=%s frameworks=%s monorepo_tooling=%s unsupported_signals=%s",
                package_manager,
                sorted(frameworks),
                monorepo_tooling,
                unsupported_signals,
            )
            is_monorepo = bool(monorepo_tooling) or any(
                (root / name).exists() for name in ("apps", "packages")
            )
            app_roots = [
                str(path.parent.relative_to(root))
                for path in package_json_files
                if path.parent != root
            ]
            validation_commands = self._detect_validation_commands(
                package_manager=package_manager,
                package_scripts=package_scripts,
            )
            support_status, requires_bootstrap, reasons, warnings, blockers = (
                self._classify_support(
                    configs=configs,
                    spec_files=spec_files,
                    package_json_exists=bool(package_json),
                    frameworks=frameworks,
                    unsupported_signals=unsupported_signals,
                    monorepo_tooling=monorepo_tooling,
                    is_monorepo=is_monorepo,
                    app_roots=app_roots,
                    validation_commands=validation_commands,
                    package_scripts=package_scripts,
                )
            )
            profile = RepoProfile(
                repo_path=repo_path,
                branch=branch,
                support_status=support_status,
                requires_bootstrap=requires_bootstrap,
                support_reasons=reasons,
                support_warnings=warnings,
                support_blockers=blockers,
                is_monorepo=is_monorepo,
                monorepo_tooling=monorepo_tooling,
                app_roots=app_roots,
                playwright_configs=configs,
                playwright_spec_files=spec_files,
                package_manager=package_manager,
                package_scripts=package_scripts,
                lockfiles=lockfiles,
                detected_frameworks=frameworks,
                unsupported_signals=unsupported_signals,
                validation_commands=validation_commands,
            )
            self._log_profile(profile)
            logger.info("[playwright-generation] stage=repo_strategy status=completed")
            return profile
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=repo_strategy status=failed context=%s error=%s",
                context,
                exc,
            )
            raise

    def _find_package_json_files(self, root: Path) -> list[Path]:
        return [
            path
            for path in root.rglob("package.json")
            if path.is_file() and not self._is_ignored_path(path)
        ]

    def _load_root_package_json(self, root: Path) -> dict[str, Any]:
        package_json = root / "package.json"
        if not package_json.exists():
            return {}
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _collect_dependencies(self, package_json: dict[str, Any]) -> set[str]:
        dependencies: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            values = package_json.get(key, {})
            if isinstance(values, dict):
                dependencies.update(values)
        return dependencies

    def _extract_package_scripts(self, package_json: dict[str, Any]) -> dict[str, str]:
        scripts = package_json.get("scripts", {})
        if not isinstance(scripts, dict):
            return {}
        return {
            str(name): str(command)
            for name, command in scripts.items()
            if command is not None
        }

    def _relative_files(self, root: Path, pattern: str) -> list[str]:
        return [
            str(path.relative_to(root))
            for path in root.rglob(pattern)
            if path.is_file() and not self._is_ignored_path(path)
        ]

    def _find_playwright_spec_files(self, root: Path) -> list[str]:
        spec_suffixes = (
            ".spec.ts",
            ".spec.tsx",
            ".e2e.ts",
            ".e2e.tsx",
            ".test.ts",
            ".test.tsx",
            ".pw.ts",
            ".pw.tsx",
            ".playwright.ts",
            ".playwright.tsx",
        )
        return [
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
            and path.name.endswith(spec_suffixes)
            and not self._is_ignored_path(path)
            and self._looks_like_playwright_spec(path)
        ]

    def _looks_like_playwright_spec(self, path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        lower_content = content.lower()
        path_parts = {part.lower() for part in path.parts}
        return (
            "@playwright/test" in content
            or "playwright" in lower_content
            or (
                bool(path_parts.intersection({"e2e", "playwright"}))
                and "test(" in lower_content
            )
        )

    def _detect_lockfiles(self, root: Path) -> list[str]:
        lockfile_names = ("pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb")
        return [name for name in lockfile_names if (root / name).exists()]

    def _detect_package_manager(self, lockfiles: list[str]) -> str | None:
        if "pnpm-lock.yaml" in lockfiles:
            return "pnpm"
        if "yarn.lock" in lockfiles:
            return "yarn"
        if "bun.lockb" in lockfiles:
            return "bun"
        if "package-lock.json" in lockfiles:
            return "npm"
        return "npm"

    def _detect_frameworks(self, dependencies: set[str], root: Path) -> list[str]:
        frameworks: list[str] = []
        if "@angular/core" in dependencies or (root / "angular.json").exists():
            frameworks.append("angular")
        if "react" in dependencies or "next" in dependencies:
            frameworks.append("react")
        if "vue" in dependencies or "nuxt" in dependencies:
            frameworks.append("vue")
        if "svelte" in dependencies or "@sveltejs/kit" in dependencies:
            frameworks.append("svelte")
        return frameworks

    def _detect_monorepo_tooling(
        self,
        root: Path,
        dependencies: set[str],
    ) -> list[str]:
        tooling: list[str] = []
        if (root / "nx.json").exists() or "nx" in dependencies:
            tooling.append("nx")
        if (root / "turbo.json").exists() or "turbo" in dependencies:
            tooling.append("turbo")
        if (root / "pnpm-workspace.yaml").exists():
            tooling.append("pnpm-workspace")
        if (root / "lerna.json").exists() or "lerna" in dependencies:
            tooling.append("lerna")
        if (root / "WORKSPACE").exists() or (root / "MODULE.bazel").exists():
            tooling.append("bazel")
        return tooling

    def _detect_unsupported_signals(
        self,
        root: Path,
        dependencies: set[str],
    ) -> list[str]:
        signals: list[str] = []
        if (root / "cypress.config.ts").exists() or (root / "cypress.config.js").exists():
            signals.append("cypress")
        if "cypress" in dependencies:
            signals.append("cypress")
        selenium_dependencies = {"selenium-webdriver", "webdriverio", "nightwatch"}
        if dependencies.intersection(selenium_dependencies):
            signals.append("selenium_or_webdriver")
        if any(self._relative_files(root, pattern) for pattern in ("*.spec.py", "*.spec.java", "*.feature")):
            signals.append("non_typescript_or_bdd_tests")
        return sorted(set(signals))

    def _detect_validation_commands(
        self,
        package_manager: str | None,
        package_scripts: dict[str, Any],
    ) -> list[str]:
        if not package_manager:
            return []
        commands: list[str] = []
        for script in ("lint", "typecheck", "test:e2e", "e2e", "playwright:test", "test"):
            if script in package_scripts:
                commands.append(f"{package_manager} run {script}")
        return commands

    def _classify_support(
        self,
        *,
        configs: list[str],
        spec_files: list[str],
        package_json_exists: bool,
        frameworks: list[str],
        unsupported_signals: list[str],
        monorepo_tooling: list[str],
        is_monorepo: bool,
        app_roots: list[str],
        validation_commands: list[str],
        package_scripts: dict[str, Any] | None = None,
    ) -> tuple[str, bool, list[str], list[str], list[str]]:
        reasons: list[str] = []
        warnings: list[str] = []
        blockers: list[str] = []
        requires_bootstrap = False

        if unsupported_signals:
            blockers.append(
                "Repository contains unsupported test framework signals: "
                + ", ".join(unsupported_signals)
            )
        if not package_json_exists:
            blockers.append("No root package.json found")

        # A UI repo with no Playwright at all is not a misfit — it is a bootstrap
        # candidate: the framework (config, dependency, e2e/ convention, first spec)
        # is scaffolded during generation. Bootstrap requires a recognizable beta
        # frontend and no competing test framework; otherwise the original blockers
        # stand.
        # Eligibility is discovery-driven, not framework-hardcoded: any detected
        # frontend framework qualifies, and so does a repo whose package scripts
        # show a runnable dev server (start/dev/serve) even when the framework is
        # not one we recognize.
        scripts = package_scripts or {}
        has_dev_server_script = any(name in scripts for name in ("start", "dev", "serve"))
        playwright_missing = not configs and not spec_files
        bootstrap_eligible = (
            playwright_missing
            and package_json_exists
            and not unsupported_signals
            and (bool(frameworks) or has_dev_server_script)
        )
        if bootstrap_eligible:
            requires_bootstrap = True
            warnings.append(
                "No Playwright framework detected; bootstrap mode will scaffold "
                "config, dependencies, e2e/ convention, and the first spec"
            )
            reasons.append("Beta frontend detected without E2E framework (bootstrap)")
        else:
            if not configs and not spec_files:
                blockers.append("No Playwright config found")
                blockers.append("No TypeScript Playwright spec files found")
            elif not configs:
                warnings.append(
                    "Playwright specs exist without a Playwright config; targeted "
                    "execution may need configuration"
                )
            elif not spec_files:
                warnings.append(
                    "Playwright config exists but no specs yet; the first spec will "
                    "be created"
                )
        if not any(framework in {"angular", "react"} for framework in frameworks):
            warnings.append("No Angular or React framework signal detected")
        if not validation_commands:
            warnings.append("No package validation scripts detected")
        if is_monorepo:
            if not app_roots:
                warnings.append("Monorepo detected but no package app roots found")
            reasons.append("Monorepo detected")
        if len(configs) > 1:
            warnings.append("Multiple Playwright configs detected; ownership may be ambiguous")
        if monorepo_tooling and any(tool in {"nx", "turbo", "bazel"} for tool in monorepo_tooling):
            warnings.append(
                "Complex monorepo tooling detected; may require adapter-specific ownership logic"
            )

        if package_json_exists:
            reasons.append("Root package.json found")
        if configs:
            reasons.append("Playwright config found")
        if spec_files:
            reasons.append("TypeScript Playwright specs found")
        if any(framework in {"angular", "react"} for framework in frameworks):
            reasons.append("Primary beta frontend framework detected")
        if validation_commands:
            reasons.append("Validation scripts detected")

        if blockers:
            return "unsupported", False, reasons, warnings, blockers
        if warnings:
            return "supported_with_warnings", requires_bootstrap, reasons, warnings, blockers
        return "supported", requires_bootstrap, reasons, warnings, blockers

    def _is_ignored_path(self, path: Path) -> bool:
        ignored_parts = {
            ".git",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".next",
            ".turbo",
            ".nx",
        }
        return bool(set(path.parts).intersection(ignored_parts))

    def _log_profile(self, profile: RepoProfile) -> None:
        logger.info(
            "[playwright-generation] stage=repo_strategy support_status=%s "
            "requires_bootstrap=%s "
            "playwright_configs=%s playwright_specs=%s reasons=%s warnings=%s blockers=%s",
            profile.support_status,
            profile.requires_bootstrap,
            len(profile.playwright_configs),
            len(profile.playwright_spec_files),
            profile.support_reasons,
            profile.support_warnings,
            profile.support_blockers,
        )
