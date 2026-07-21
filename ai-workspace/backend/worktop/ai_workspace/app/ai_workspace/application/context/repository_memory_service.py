from __future__ import annotations
import hashlib
from pathlib import Path
from worktop.ai_workspace.app.common.data_governance import DataGovernanceService
from worktop.ai_workspace.app.common.path_safety import resolve_within_root

INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".ai-workspace/instructions.md")

class RepositoryMemoryService:
    """Hybrid context: repository-owned instructions plus external learned summaries."""
    def __init__(self, memory_root: str) -> None:
        self.root = Path(memory_root) / "ai-workspace-memory"
        self.governance = DataGovernanceService()

    def load(self, repository: str) -> str:
        sections: list[str] = []
        for relative in INSTRUCTION_FILES:
            path = resolve_within_root(repository, relative)
            if path.is_file():
                released = self.governance.release(relative, path.read_text(encoding="utf-8", errors="ignore")[:20000])
                if released: sections.append(f"## Repository instructions: {relative}\n{released}")
        memory = self._path(repository)
        if memory.is_file(): sections.append(f"## AI Workspace learned context\n{memory.read_text(encoding='utf-8')[:20000]}")
        return "\n\n".join(sections)

    def remember(self, repository: str, root_cause: str, evidence: list[str], files: list[str]) -> None:
        path = self._path(repository); path.parent.mkdir(parents=True, exist_ok=True)
        entry = "\n\n### Validated workspace finding\n" + f"- Root cause: {root_cause}\n- Evidence: {'; '.join(evidence[:8])}\n- Files: {', '.join(files[:12])}\n"
        existing = path.read_text(encoding="utf-8") if path.exists() else "# AI Workspace Repository Memory\n"
        path.write_text((existing + entry)[-50000:], encoding="utf-8")

    def _path(self, repository: str) -> Path:
        key = hashlib.sha256(str(Path(repository).resolve()).encode()).hexdigest()[:20]
        return self.root / key / "context.md"
