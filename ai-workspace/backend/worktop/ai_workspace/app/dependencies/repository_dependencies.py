from worktop.ai_workspace.app.dependencies.container import container
from worktop.ai_workspace.app.repository.application.file_read_service import FileReadService
from worktop.ai_workspace.app.repository.application.file_write_service import FileWriteService
from worktop.ai_workspace.app.repository.application.git_diff_service import GitDiffService
from worktop.ai_workspace.app.repository.application.repository_scan_service import RepositoryScanService
from worktop.ai_workspace.app.repository.application.repository_search_service import RepositorySearchService
from worktop.ai_workspace.app.repository.application.repository_tree_service import RepositoryTreeService


def get_repository_scan_service() -> RepositoryScanService:
    return container.repository_scan_service


def get_repository_tree_service() -> RepositoryTreeService:
    return container.repository_tree_service


def get_repository_search_service() -> RepositorySearchService:
    return container.repository_search_service


def get_file_read_service() -> FileReadService:
    return container.file_read_service


def get_file_write_service() -> FileWriteService:
    return container.file_write_service


def get_git_diff_service() -> GitDiffService:
    return container.git_diff_service
