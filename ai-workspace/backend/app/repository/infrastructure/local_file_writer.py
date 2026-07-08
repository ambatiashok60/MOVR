from app.common.path_safety import resolve_within_root


class LocalFileWriter:
    """The only place in the codebase allowed to write to a workspace path. Used exclusively
    by apply_patch_tool.py (via review_service.py's apply flow) — never called directly from
    a route or from Ask mode, which has no write tools registered at all."""

    def write_file(self, root: str, relative_path: str, content: str) -> None:
        target = resolve_within_root(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def delete_file(self, root: str, relative_path: str) -> None:
        target = resolve_within_root(root, relative_path)
        if target.exists():
            target.unlink()
