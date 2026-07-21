from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from worktop.api_agent.app.config import settings
from worktop.api_agent.app.schemas.generation_manifest import (
    GenerationManifest,
    ManifestArtifact,
    ManifestDecision,
)
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.repository_policy import RepositoryPolicy
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_RECORDED_SETTINGS = (
    "max_generation_repair_attempts",
    "max_execution_repair_attempts",
    "enable_test_execution",
    "execution_timeout_seconds",
)


class GenerationManifestService:
    """Record the frozen inputs and decisions of a generation run."""

    def build(
        self,
        task_id: str,
        repo_path: str,
        *,
        branch: str | None = None,
        profile: RepoProfile | None = None,
        policy: RepositoryPolicy | None = None,
        model_provider: str = "unknown",
        story_material: list[str] | None = None,
        decisions: list[tuple[str, str, str]] | None = None,
        artifacts: list[tuple[str, str]] | None = None,
    ) -> GenerationManifest:
        manifest = GenerationManifest(
            task_id=task_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            repo_path=repo_path,
            branch=branch,
            repository_snapshot_digest=self._snapshot_digest(profile),
            model_provider=model_provider,
            prompt_versions=self.prompt_versions(),
            settings_snapshot={
                name: str(getattr(settings, name)) for name in _RECORDED_SETTINGS
            },
            policy_source=policy.source if policy else "defaults",
            policy_snapshot=(
                {k: str(v) for k, v in policy.generation.model_dump().items()}
                if policy
                else {}
            ),
            decisions=[
                ManifestDecision(stage=stage, decision=decision, confidence=confidence)
                for stage, decision, confidence in (decisions or [])
                if decision
            ],
            artifacts=[
                ManifestArtifact(path=path, content_digest=self._digest(content))
                for path, content in (artifacts or [])
            ],
        )
        manifest.generation_fingerprint = self._fingerprint(
            manifest, story_material or []
        )
        logger.info(
            "Generation manifest built (fingerprint=%s, decisions=%s, artifacts=%s).",
            manifest.generation_fingerprint,
            len(manifest.decisions),
            len(manifest.artifacts),
        )
        return manifest

    def prompt_versions(self) -> dict[str, str]:
        """Content digest per prompt module — versions that cannot go stale."""
        versions: dict[str, str] = {}
        if not _PROMPTS_DIR.is_dir():
            return versions
        for path in sorted(_PROMPTS_DIR.glob("*.py")):
            if path.name == "__init__.py":
                continue
            versions[path.stem] = self._digest(path.read_text(encoding="utf-8"))
        return versions

    def _snapshot_digest(self, profile: RepoProfile | None) -> str:
        if profile is None:
            return ""
        digest = hashlib.sha256()
        for endpoint in sorted(
            f"{e.method} {e.path} {e.source_file}" for e in profile.endpoints
        ):
            digest.update(endpoint.encode())
        for test in sorted(candidate.path for candidate in profile.existing_tests):
            digest.update(test.encode())
        digest.update(str(sorted(profile.test_frameworks)).encode())
        return digest.hexdigest()[:16]

    def _fingerprint(
        self, manifest: GenerationManifest, story_material: list[str]
    ) -> str:
        material = "\n".join(
            [
                manifest.repository_snapshot_digest,
                *story_material,
                manifest.model_provider,
                *(f"{k}={v}" for k, v in sorted(manifest.prompt_versions.items())),
                *(f"{k}={v}" for k, v in sorted(manifest.policy_snapshot.items())),
                *(f"{k}={v}" for k, v in sorted(manifest.settings_snapshot.items())),
            ]
        )
        return self._digest(material)

    def _digest(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
