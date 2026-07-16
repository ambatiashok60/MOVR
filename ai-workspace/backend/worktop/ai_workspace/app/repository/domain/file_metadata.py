from dataclasses import dataclass


@dataclass
class FileMetadata:
    path: str
    size_bytes: int
    is_binary: bool
    language: str | None = None
