from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_FILE_CHARS = 6000
MAX_SEARCH_HITS = 20
MAX_DIR_ENTRIES = 50
IGNORED_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".next", ".turbo", ".nx"}


class RepoExplorer:
    """Sandboxed, bounded executor for model-directed exploration requests.

    Every operation is logged with the model's stated reason so a generation
    run's evidence trail is fully reconstructable.
    """

    def __init__(self, repo_path: str) -> None:
        self.root = Path(repo_path).resolve()

    def execute(self, request) -> str:
        try:
            if request.kind == "read_file":
                result = self._read_file(request.target)
            elif request.kind == "list_dir":
                result = self._list_dir(request.target)
            else:
                result = self._search(request.target)
            logger.info(
                "[playwright-generation] stage=repo_exploration kind=%s target=%s "
                "reason=%s result_chars=%s",
                request.kind, request.target, request.reason or "unstated", len(result),
            )
            return f"### {request.kind} {request.target}\n{result}"
        except Exception as exc:
            logger.info(
                "[playwright-generation] stage=repo_exploration status=failed "
                "kind=%s target=%s error=%s", request.kind, request.target, exc,
            )
            return f"### {request.kind} {request.target}\nerror: {exc}"

    def _safe(self, target: str) -> Path:
        path = (self.root / target).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError("path escapes repository root")
        return path

    def _read_file(self, target: str) -> str:
        path = self._safe(target)
        if not path.is_file():
            return "error: file does not exist"
        content = path.read_text(encoding="utf-8", errors="ignore")
        return f"{content[:MAX_FILE_CHARS]}\n… [truncated]" if len(content) > MAX_FILE_CHARS else (content or "(empty file)")

    def _list_dir(self, target: str) -> str:
        path = self._safe(target) if target not in ("", ".") else self.root
        if not path.is_dir():
            return "error: directory does not exist"
        entries = sorted(
            e.name + ("/" if e.is_dir() else "") for e in path.iterdir() if e.name not in IGNORED_DIRS
        )
        listed = entries[:MAX_DIR_ENTRIES]
        extra = f"\n… {len(entries) - MAX_DIR_ENTRIES} more omitted" if len(entries) > MAX_DIR_ENTRIES else ""
        return ("\n".join(listed) + extra) if listed else "(empty directory)"

    def _search(self, term: str) -> str:
        hits: list[str] = []
        for path in self.root.rglob("*"):
            if len(hits) >= MAX_SEARCH_HITS:
                break
            if not path.is_file() or set(path.parts).intersection(IGNORED_DIRS):
                continue
            rel = path.relative_to(self.root).as_posix()
            if term.lower() in rel.lower():
                hits.append(rel)
                continue
            try:
                if path.stat().st_size < 300_000:
                    for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if term in line:
                            hits.append(f"{rel}:{n}: {line.strip()[:160]}")
                            break
            except OSError:
                continue
        return "\n".join(hits) if hits else "(no matches)"
