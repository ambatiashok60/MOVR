from __future__ import annotations

from worktop.test_agent.app.schemas.code_patch import CodePatch, PatchSet


class PatchPlanner:
    def validate(self, patches: PatchSet) -> PatchSet:
        for patch in patches.patches:
            self._validate_patch(patch)
        return patches

    def _validate_patch(self, patch: CodePatch) -> None:
        if not patch.path:
            raise ValueError("Patch path is required")
        if patch.path.startswith("/") or ".." in patch.path.split("/"):
            raise ValueError(f"Unsafe patch path: {patch.path}")
        if patch.operation in {
            "create", "replace", "append", "append_test", "replace_test", "insert_class_member",
            "insert_object_property", "insert_import",
        } and not patch.content:
            raise ValueError(f"Patch content is required for {patch.operation}")
        if patch.operation == "replace":
            if patch.start_line is None or patch.end_line is None:
                raise ValueError("Replace patch requires start_line and end_line")
            if patch.start_line < 1 or patch.end_line < patch.start_line:
                raise ValueError("Invalid replace line range")
        if patch.operation == "append" and patch.start_line is not None and patch.start_line < 1:
            raise ValueError("Append insertion line must be 1 or greater")
        if patch.operation == "append_test" and not patch.target_describe_title:
            raise ValueError("append_test requires target_describe_title")
        if patch.operation in {"insert_class_member", "insert_object_property"}:
            if not patch.target_symbol or not patch.member_name:
                raise ValueError(
                    f"{patch.operation} requires target_symbol and member_name"
                )
        if patch.operation == "replace_test" and not patch.target_test_title:
            raise ValueError("replace_test requires target_test_title")
