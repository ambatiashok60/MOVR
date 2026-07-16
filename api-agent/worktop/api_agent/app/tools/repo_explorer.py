from __future__ import annotations

from pathlib import Path
from worktop.api_agent.app.security.data_governance_service import DataGovernanceService

MAX_FILE_CHARS = 6000
MAX_SEARCH_HITS = 20
MAX_DIR_ENTRIES = 50
IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "target",
    "coverage", ".venv", "venv", "__pycache__",
}


class RepoExplorer:
    """Sandboxed, bounded executor for model-directed exploration requests.

    Shared by every agentic tool loop (discovery, scenario planning, code
    generation): read_file / search / list_dir inside the repo root only, with
    hard caps on payload size.
    """

    def execute(self, root: Path, request) -> str:
        from worktop.api_agent.app.utils.logging_utils import log_step

        try:
            result = self._dispatch(root, request)
            log_step(
                "repo_explorer_operation",
                {"kind": request.kind, "target": request.target, "result_chars": len(result)},
            )
            return result
        except Exception as exc:
            log_step(
                "repo_explorer_operation_failed",
                {"kind": request.kind, "target": request.target, "error": str(exc)},
            )
            return f"### {request.kind} {request.target}\nerror: {exc}"

    def _dispatch(self, root: Path, request) -> str:
        try:
            if request.kind == "read_file":
                return f"### read_file {request.target}\n{self.read_file(root, request.target)}"
            if request.kind == "list_dir":
                return f"### list_dir {request.target}\n{self.list_dir(root, request.target)}"
            return f"### search {request.target}\n{self.search(root, request.target)}"
        except Exception as exc:
            return f"### {request.kind} {request.target}\nerror: {exc}"

    def read_file(self, root: Path, target: str) -> str:
        from worktop.api_agent.app.tools.path_safety import safe_join

        path = safe_join(root, target)
        if not path.is_file():
            return "error: file does not exist"
        content = path.read_text(encoding="utf-8", errors="ignore")
        released = self.governance.release_file(target, content)
        if released is None:
            return "error: file is restricted by the repository data policy"
        content = released
        if len(content) > MAX_FILE_CHARS:
            return f"{content[:MAX_FILE_CHARS]}\n… [truncated]"
        return content or "(empty file)"

    def list_dir(self, root: Path, target: str) -> str:
        from worktop.api_agent.app.tools.path_safety import safe_join

        path = safe_join(root, target) if target not in ("", ".") else root
        if not path.is_dir():
            return "error: directory does not exist"
        entries = sorted(
            entry.name + ("/" if entry.is_dir() else "")
            for entry in path.iterdir()
            if entry.name not in IGNORED_DIRS
        )
        listed = entries[:MAX_DIR_ENTRIES]
        suffix = (
            f"\n… {len(entries) - MAX_DIR_ENTRIES} more entries omitted"
            if len(entries) > MAX_DIR_ENTRIES
            else ""
        )
        return "\n".join(listed) + suffix if listed else "(empty directory)"

    def search(self, root: Path, term: str) -> str:
        hits: list[str] = []
        for path in root.rglob("*"):
            if len(hits) >= MAX_SEARCH_HITS:
                break
            if not path.is_file() or set(path.parts).intersection(IGNORED_DIRS):
                continue
            relative = path.relative_to(root).as_posix()
            if self.governance.classify(relative) == "restricted":
                continue
            if term.lower() in relative.lower():
                hits.append(relative)
                continue
            try:
                if path.stat().st_size < 300_000:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    content = self.governance.release_file(relative, content) or ""
                    for line_number, line in enumerate(content.splitlines(), 1):
                        if term in line:
                            hits.append(f"{relative}:{line_number}: {line.strip()[:160]}")
                            break
            except OSError:
                continue
        return "\n".join(hits) if hits else "(no matches)"
    def __init__(self, governance: DataGovernanceService | None = None) -> None:
        self.governance = governance or DataGovernanceService()
