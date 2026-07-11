from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from worktop.test_agent.app.config import settings
from worktop.test_agent.app.logging_config import log_event
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.generation_manifest import (
    GenerationManifest,
    ManifestDecision,
    ManifestPatch,
)
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.repository_policy import RepositoryPolicy
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_RECORDED_SETTINGS = (
    "max_repair_attempts",
    "min_placement_confidence",
    "min_action_confidence",
    "min_ownership_confidence",
    "min_flow_merge_confidence",
    "validation_timeout_seconds",
)


class GenerationManifestService:
    """Record the frozen inputs and decisions of a generation run."""

    def build(
        self,
        request: GenerationRequest,
        *,
        inventory: RepositoryInventory | None = None,
        policy: RepositoryPolicy | None = None,
        model_provider: str = "unknown",
        decisions: list[tuple[str, Any]] | None = None,
        patches: PatchSet | None = None,
    ) -> GenerationManifest:
        patches = patches or PatchSet()
        manifest = GenerationManifest(
            job_id=request.job_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            repo_path=request.repo_path,
            branch=request.branch,
            repo_head=inventory.repo_head if inventory else None,
            repository_snapshot_digest=self._snapshot_digest(inventory),
            model_provider=model_provider,
            prompt_versions=self.prompt_versions(),
            settings_snapshot={
                name: str(getattr(settings, name)) for name in _RECORDED_SETTINGS
            },
            policy_source=policy.source if policy else "defaults",
            policy_snapshot=(
                {
                    key: str(value)
                    for key, value in policy.generation.model_dump().items()
                }
                if policy
                else {}
            ),
            decisions=[
                ManifestDecision(
                    stage=stage,
                    decision=self._decision_label(decision),
                    confidence=float(getattr(decision, "confidence", 0.0) or 0.0),
                )
                for stage, decision in (decisions or [])
                if decision is not None
            ],
            patches=[
                ManifestPatch(
                    path=patch.path,
                    operation=patch.operation,
                    content_digest=self._digest(patch.content),
                )
                for patch in patches.patches
            ],
        )
        manifest.generation_fingerprint = self._fingerprint(manifest, request)
        log_event(
            logger,
            logging.INFO,
            "generation_manifest",
            "built",
            job_id=request.job_id,
            fingerprint=manifest.generation_fingerprint,
            repo_head=manifest.repo_head or "unknown",
            decisions=len(manifest.decisions),
            patches=len(manifest.patches),
        )
        return manifest

    def prompt_versions(self) -> dict[str, str]:
        """Content digest per prompt module.

        Hashing the prompt sources means a prompt edit changes the recorded
        version automatically — no manually-bumped constant can go stale.
        """
        versions: dict[str, str] = {}
        if not _PROMPTS_DIR.is_dir():
            return versions
        for path in sorted(_PROMPTS_DIR.glob("*.py")):
            if path.name == "__init__.py":
                continue
            versions[path.stem] = self._digest(path.read_text(encoding="utf-8"))
        return versions

    def _snapshot_digest(self, inventory: RepositoryInventory | None) -> str:
        if inventory is None or not inventory.file_hashes:
            return ""
        digest = hashlib.sha256()
        for path in sorted(inventory.file_hashes):
            digest.update(f"{path}:{inventory.file_hashes[path]}\n".encode())
        return digest.hexdigest()[:16]

    def _fingerprint(
        self, manifest: GenerationManifest, request: GenerationRequest
    ) -> str:
        material = "\n".join(
            [
                manifest.repository_snapshot_digest,
                manifest.repo_head or "",
                request.test_case_name,
                *request.steps,
                manifest.model_provider,
                *(f"{k}={v}" for k, v in sorted(manifest.prompt_versions.items())),
                *(f"{k}={v}" for k, v in sorted(manifest.policy_snapshot.items())),
                *(f"{k}={v}" for k, v in sorted(manifest.settings_snapshot.items())),
            ]
        )
        return self._digest(material)

    def _decision_label(self, decision: Any) -> str:
        for attribute in ("action", "decision", "target_spec_file", "owner_path"):
            value = getattr(decision, attribute, None)
            if isinstance(value, str) and value:
                return value
        return str(decision)[:80]

    def _digest(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
