from __future__ import annotations
import ast
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from app.ai_workspace.domain.agent_turn import AgentFileChange

@dataclass
class PatchValidationResult:
    passed: bool
    findings: list[str] = field(default_factory=list)

class PatchValidationService:
    """Deterministic pre-review validation that never mutates the workspace."""
    def validate(self, changes: list[AgentFileChange]) -> PatchValidationResult:
        findings: list[str] = []
        seen: set[str] = set()
        for change in changes:
            path = PurePosixPath(change.path)
            if path.is_absolute() or ".." in path.parts:
                findings.append(f"Unsafe path: {change.path}")
                continue
            if change.path in seen:
                findings.append(f"Duplicate file proposal: {change.path}")
            seen.add(change.path)
            if change.status != "deleted" and not change.new_content.strip():
                findings.append(f"Empty generated content: {change.path}")
                continue
            if change.status == "deleted":
                findings.append(f"File deletion requires explicit high-risk review: {change.path}")
            try:
                if path.suffix == ".py" and change.status != "deleted":
                    ast.parse(change.new_content)
                elif path.suffix == ".json" and change.status != "deleted":
                    json.loads(change.new_content)
            except (SyntaxError, json.JSONDecodeError) as exc:
                findings.append(f"Syntax validation failed for {change.path}: {exc}")
        blocking = [item for item in findings if "requires explicit" not in item]
        return PatchValidationResult(passed=not blocking, findings=findings)
