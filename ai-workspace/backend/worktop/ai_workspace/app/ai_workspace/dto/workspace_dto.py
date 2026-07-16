from .base import CamelModel


class ValidatePathRequest(CamelModel):
    path: str


class RepositoryMetadataDto(CamelModel):
    id: str
    name: str
    path: str
    default_branch: str


class WorkspaceInfoDto(CamelModel):
    path: str
    validation_state: str
    validation_message: str | None = None
    repository: RepositoryMetadataDto | None = None


class FileNodeDto(CamelModel):
    id: str
    name: str
    path: str
    type: str  # "file" | "folder"
    status: str | None = None
    children: list["FileNodeDto"] | None = None


FileNodeDto.model_rebuild()
