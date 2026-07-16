from dataclasses import dataclass


@dataclass
class SelectedFile:
    path: str
    is_priority: bool = False
