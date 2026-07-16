import subprocess

from worktop.ai_workspace.app.common.path_safety import resolve_within_root


class GitCliProvider:
    """Thin wrapper around the `git` CLI. Assumes git is installed on the host running the
    backend — no bundled/vendored git client. Every method scopes to a single repo root and
    never accepts arbitrary shell input (arguments are passed as a list, not interpolated
    into a shell string, to avoid command injection from LLM-influenced paths)."""

    def status(self, root: str) -> str:
        return self._run(root, ["git", "status", "--short"])

    def diff(self, root: str, relative_path: str | None = None) -> str:
        args = ["git", "diff"]
        if relative_path:
            resolve_within_root(root, relative_path)  # validate before shelling out
            args.append(relative_path)
        return self._run(root, args)

    def current_branch(self, root: str) -> str:
        return self._run(root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()

    def list_branches(self, root: str) -> list[str]:
        output = self._run(root, ["git", "branch", "--format=%(refname:short)"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _run(self, root: str, args: list[str]) -> str:
        result = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git command failed: {' '.join(args)}\n{result.stderr}")
        return result.stdout
