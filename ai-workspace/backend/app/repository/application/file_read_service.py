from app.repository.domain.repository_file import RepositoryFile
from app.repository.application.repository_access_service import RepositoryAccessService


class FileReadService:
    def __init__(self, access_service: RepositoryAccessService):
        self._access_service = access_service

    def read(self, root: str, relative_path: str) -> RepositoryFile:
        return self._access_service.read_file(root, relative_path)
