from __future__ import annotations

from pydantic import BaseModel, Field


class ManifestDecision(BaseModel):
    stage: str
    decision: str
    confidence: float = 0.0


class ManifestPatch(BaseModel):
    path: str
    operation: str
    content_digest: str


class GenerationManifest(BaseModel):
    """Everything needed to explain — and reproduce — one generation run.

    The same story against the same repository should be explainable when it
    produces a different output: the manifest freezes the repository snapshot,
    prompt versions, model, policy, settings, decisions, and patch digests so
    two runs can be diffed input-by-input.
    """

    job_id: str
    created_at: str
    repo_path: str
    branch: str | None = None
    repo_head: str | None = None
    repository_snapshot_digest: str = ""
    model_provider: str = "unknown"
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    settings_snapshot: dict[str, str] = Field(default_factory=dict)
    policy_source: str = "defaults"
    policy_snapshot: dict[str, str] = Field(default_factory=dict)
    decisions: list[ManifestDecision] = Field(default_factory=list)
    patches: list[ManifestPatch] = Field(default_factory=list)
    generation_fingerprint: str = ""
