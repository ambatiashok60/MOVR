from dataclasses import dataclass
from datetime import datetime

from .workspace_mode import WorkspaceMode


@dataclass
class WorkspaceSession:
    id: str
    tenant_id: str
    repository_path: str
    branch: str
    mode: WorkspaceMode
    current_task: str | None
    started_at: datetime
    last_activity_at: datetime
