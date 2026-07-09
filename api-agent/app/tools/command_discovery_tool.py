from __future__ import annotations

import json
from pathlib import Path

from app.tools.path_safety import resolve_workspace_path


class CommandDiscoveryTool:
    def discover(self, repo_path: str) -> dict[str, str | list[str] | None]:
        root = resolve_workspace_path(repo_path)
        commands: list[str] = []
        ci_command: str | None = None
        stage_command: str | None = None

        if (root / "pom.xml").exists():
            ci_command = "mvn test"
            stage_command = "mvn verify -Pstage"
            commands.extend(["mvn test", "mvn verify"])
        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            ci_command = "./gradlew test"
            stage_command = "./gradlew integrationTest"
            commands.extend(["./gradlew test", "./gradlew integrationTest"])

        package_json = root / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    ci_command = ci_command or "npm test"
                    commands.append("npm test")
                for name in scripts:
                    if "stage" in name or "integration" in name or "e2e" in name:
                        stage_command = stage_command or f"npm run {name}"
                        commands.append(f"npm run {name}")
            except Exception:
                pass

        if self._has_python_tests(root):
            ci_command = ci_command or "pytest"
            commands.append("pytest")
            if (root / "tests" / "stage").exists():
                stage_command = stage_command or "pytest tests/stage"
                commands.append("pytest tests/stage")

        return {
            "ci_command": ci_command,
            "stage_command": stage_command,
            "validation_commands": list(dict.fromkeys(commands)),
        }

    def _has_python_tests(self, root: Path) -> bool:
        return any(
            (root / name).exists()
            for name in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")
        ) or (root / "tests").exists()
