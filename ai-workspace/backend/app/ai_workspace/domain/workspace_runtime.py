from dataclasses import dataclass, field

from .workspace_mode import WorkspaceMode


@dataclass
class WorkspaceRuntime:
    """Active state for one open workspace path — not persisted long-term, held in
    SQLite by default for V1, with an optional in-memory store for throwaway demos."""

    workspace_path: str
    session_id: str
    selected_model_id: str | None = None
    selected_file_paths: list[str] = field(default_factory=list)
    enabled_tool_ids: list[str] = field(default_factory=list)
    mode: WorkspaceMode = WorkspaceMode.AGENT
