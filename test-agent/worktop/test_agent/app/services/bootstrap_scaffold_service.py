from __future__ import annotations

import json
from pathlib import Path

from worktop.test_agent.app.schemas.code_patch import CodePatch, PatchSet
from worktop.test_agent.app.schemas.repo_profile import RepoProfile
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)

PLAYWRIGHT_DEV_DEPENDENCY = "^1.50.0"


class BootstrapScaffoldService:
    """Deterministic Playwright framework scaffold for repos with no E2E setup.

    Bootstrap repos get their config, dependency, npm script, and fixtures
    convention from deterministic templates governed by Playwright best practices
    — only the spec itself is LLM-generated. On path collision the deterministic
    scaffold wins over generated patches.
    """

    def merge(
        self,
        repo_path: str,
        repo_profile: RepoProfile,
        patches: PatchSet,
    ) -> PatchSet:
        scaffold = self.build_scaffold_patches(repo_path, repo_profile)
        scaffold_paths = {patch.path for patch in scaffold}
        kept: list[CodePatch] = []
        for patch in patches.patches:
            if patch.path in scaffold_paths:
                logger.info(
                    "[playwright-generation] stage=bootstrap_scaffold "
                    "status=dropped_generated_duplicate path=%s",
                    patch.path,
                )
                continue
            kept.append(patch)
        return PatchSet(patches=scaffold + kept)

    def build_scaffold_patches(
        self,
        repo_path: str,
        repo_profile: RepoProfile,
    ) -> list[CodePatch]:
        patches: list[CodePatch] = []
        root = Path(repo_path)

        config_patch = self._playwright_config_patch(root, repo_profile)
        if config_patch is not None:
            patches.append(config_patch)

        package_patch = self._package_json_patch(root)
        if package_patch is not None:
            patches.append(package_patch)

        fixtures_patch = self._fixtures_patch(root)
        if fixtures_patch is not None:
            patches.append(fixtures_patch)

        logger.info(
            "[playwright-generation] stage=bootstrap_scaffold status=built patches=%s "
            "paths=%s",
            len(patches),
            [patch.path for patch in patches],
        )
        return patches

    def _playwright_config_patch(
        self,
        root: Path,
        repo_profile: RepoProfile,
    ) -> CodePatch | None:
        if (root / "playwright.config.ts").exists():
            return None
        base_url = self._default_base_url(repo_profile)
        web_server = self._web_server_block(repo_profile, base_url)
        content = f"""import {{ defineConfig, devices }} from '@playwright/test';

export default defineConfig({{
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['html', {{ open: 'never' }}], ['list']],
  use: {{
    baseURL: process.env.BASE_URL ?? '{base_url}',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  }},
  projects: [
    {{ name: 'chromium', use: {{ ...devices['Desktop Chrome'] }} }},
  ],{web_server}
}});
"""
        return CodePatch(
            path="playwright.config.ts",
            operation="create",
            content=content,
            reason="Bootstrap: Playwright config scaffolded for a repo without E2E setup.",
        )

    def _default_base_url(self, repo_profile: RepoProfile) -> str:
        if "angular" in repo_profile.detected_frameworks:
            return "http://localhost:4200"
        return "http://localhost:3000"

    def _web_server_block(self, repo_profile: RepoProfile, base_url: str) -> str:
        scripts = repo_profile.package_scripts
        dev_script = next(
            (name for name in ("start", "dev", "serve") if name in scripts),
            None,
        )
        if dev_script is None:
            return ""
        package_manager = repo_profile.package_manager or "npm"
        return f"""
  webServer: {{
    command: '{package_manager} run {dev_script}',
    url: '{base_url}',
    reuseExistingServer: !process.env.CI,
  }},"""

    def _package_json_patch(self, root: Path) -> CodePatch | None:
        package_json_path = root / "package.json"
        if not package_json_path.exists():
            logger.warning(
                "[playwright-generation] stage=bootstrap_scaffold "
                "status=missing_package_json"
            )
            return None
        original = package_json_path.read_text(encoding="utf-8")
        try:
            data = json.loads(original)
        except json.JSONDecodeError:
            logger.warning(
                "[playwright-generation] stage=bootstrap_scaffold "
                "status=unparseable_package_json"
            )
            return None
        if not isinstance(data, dict):
            return None

        changed = False
        dev_dependencies = data.setdefault("devDependencies", {})
        if isinstance(dev_dependencies, dict) and "@playwright/test" not in dev_dependencies:
            dev_dependencies["@playwright/test"] = PLAYWRIGHT_DEV_DEPENDENCY
            changed = True
        scripts = data.setdefault("scripts", {})
        if isinstance(scripts, dict) and "test:e2e" not in scripts:
            scripts["test:e2e"] = "playwright test"
            changed = True
        if not changed:
            return None

        content = json.dumps(data, indent=2) + "\n"
        return CodePatch(
            path="package.json",
            operation="replace",
            start_line=1,
            end_line=len(original.splitlines()),
            content=content,
            reason="Bootstrap: add @playwright/test devDependency and test:e2e script.",
        )

    def _fixtures_patch(self, root: Path) -> CodePatch | None:
        if (root / "e2e" / "fixtures.ts").exists():
            return None
        content = """import { test as base, expect } from '@playwright/test';

// Central fixture entry point for this repo's E2E suite.
// Extend `base` with auth/session, test data, or page-object fixtures as
// coverage grows, so specs keep importing from this single module.
export const test = base;
export { expect };
"""
        return CodePatch(
            path="e2e/fixtures.ts",
            operation="create",
            content=content,
            reason="Bootstrap: shared fixtures entry point for the new E2E suite.",
        )
