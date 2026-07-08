from dataclasses import dataclass, field


@dataclass
class RepositoryTreeNode:
    id: str
    name: str
    path: str
    type: str  # "file" | "folder"
    status: str | None = None  # "M" | "A" | "D" | None, from git status
    children: list["RepositoryTreeNode"] = field(default_factory=list)
