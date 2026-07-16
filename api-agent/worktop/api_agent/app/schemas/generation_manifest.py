from __future__ import annotations

from pydantic import BaseModel, Field


class ManifestDecision(BaseModel):
    stage: str
    decision: str
    confidence: str = ""


class ManifestArtifact(BaseModel):
    path: str
    content_digest: str


class GenerationManifest(BaseModel):
    """Everything needed to explain — and reproduce — one generation run.

    Freezes the repository snapshot, prompt versions, model, settings, policy,
    decisions, and artifact digests so two runs can be diffed input-by-input
    when the same story produces different output.
    """

    task_id: str
    created_at: str
    repo_path: str
    branch: str | None = None
    repository_snapshot_digest: str = ""
    model_provider: str = "unknown"
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    settings_snapshot: dict[str, str] = Field(default_factory=dict)
    policy_source: str = "defaults"
    policy_snapshot: dict[str, str] = Field(default_factory=dict)
    decisions: list[ManifestDecision] = Field(default_factory=list)
    artifacts: list[ManifestArtifact] = Field(default_factory=list)
    generation_fingerprint: str = ""
