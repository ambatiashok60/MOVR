import difflib

from worktop.ai_workspace.app.ai_workspace.domain.file_change import DiffHunk, DiffLine


class DiffService:
    """Computes display diff_hunks from (old_content, new_content). This is the only place
    that builds DiffHunk/DiffLine — file_change.py's docstring explains why nothing should
    ever reconstruct file content from these hunks (they're display-only, lossy by design)."""

    def build_hunks(self, old_content: str, new_content: str, context_lines: int = 3) -> list[DiffHunk]:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)

        hunks: list[DiffHunk] = []
        for group in matcher.get_grouped_opcodes(context_lines):
            lines: list[DiffLine] = []
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for offset, old_line in enumerate(old_lines[i1:i2]):
                        lines.append(
                            DiffLine(type="context", old_line_number=i1 + offset + 1, new_line_number=j1 + offset + 1, content=old_line)
                        )
                else:
                    if tag in ("replace", "delete"):
                        for offset, old_line in enumerate(old_lines[i1:i2]):
                            lines.append(DiffLine(type="removed", old_line_number=i1 + offset + 1, new_line_number=None, content=old_line))
                    if tag in ("replace", "insert"):
                        for offset, new_line in enumerate(new_lines[j1:j2]):
                            lines.append(DiffLine(type="added", old_line_number=None, new_line_number=j1 + offset + 1, content=new_line))

            first_old, last_old = group[0][1], group[-1][2]
            first_new, last_new = group[0][3], group[-1][4]
            header = f"@@ -{first_old + 1},{last_old - first_old} +{first_new + 1},{last_new - first_new} @@"
            hunks.append(DiffHunk(header=header, lines=lines))

        return hunks

    def count_changes(self, hunks: list[DiffHunk]) -> tuple[int, int]:
        additions = sum(1 for hunk in hunks for line in hunk.lines if line.type == "added")
        deletions = sum(1 for hunk in hunks for line in hunk.lines if line.type == "removed")
        return additions, deletions
