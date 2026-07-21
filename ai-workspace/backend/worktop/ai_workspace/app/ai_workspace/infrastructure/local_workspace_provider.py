from pathlib import Path


class LocalWorkspaceProvider:
    """Validates a local filesystem path as a usable workspace root. Deliberately does not
    decide 'has source files' itself — that's repository_scan_service.py's job — this only
    checks the path is real, is a directory, and is readable."""

    def exists_and_is_directory(self, path: str) -> bool:
        p = Path(path)
        return p.exists() and p.is_dir()

    def has_git(self, path: str) -> bool:
        return (Path(path) / ".git").exists()
