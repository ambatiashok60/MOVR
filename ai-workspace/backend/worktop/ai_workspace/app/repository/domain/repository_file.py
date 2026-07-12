from dataclasses import dataclass

from .file_metadata import FileMetadata


@dataclass
class RepositoryFile:
    metadata: FileMetadata
    content: str
