from fastapi import APIRouter, Depends, HTTPException

from app.ai_workspace.application.workspace_path_service import WorkspacePathService
from app.ai_workspace.dto.workspace_dto import FileNodeDto, ValidatePathRequest, WorkspaceInfoDto, RepositoryMetadataDto
from app.config.settings import get_settings
from app.dependencies.ai_workspace_dependencies import get_workspace_path_service
from app.dependencies.container import container
from app.dependencies.repository_dependencies import get_file_read_service, get_repository_tree_service
from app.repository.application.file_read_service import FileReadService
from app.repository.application.repository_tree_service import RepositoryTreeService

router = APIRouter(prefix="/ai-workspace", tags=["Workspace"])


@router.post("/workspace/validate", response_model=WorkspaceInfoDto)
def validate_path(
    request: ValidatePathRequest, service: WorkspacePathService = Depends(get_workspace_path_service)
) -> WorkspaceInfoDto:
    result = service.validate(request.path)
    repository = None
    if result.is_valid and result.repository_id:
        repository = RepositoryMetadataDto(
            id=result.repository_id, name=request.path.rstrip("/").split("/")[-1], path=request.path, default_branch="main"
        )
    return WorkspaceInfoDto(
        path=result.path,
        validation_state="valid" if result.is_valid else "invalid",
        validation_message=result.message,
        repository=repository,
    )


@router.post("/workspace/validate-path", response_model=WorkspaceInfoDto)
def validate_path_legacy(
    request: ValidatePathRequest, service: WorkspacePathService = Depends(get_workspace_path_service)
) -> WorkspaceInfoDto:
    return validate_path(request, service)


@router.get("/repositories")
def list_repositories() -> list[dict]:
    repositories = []
    for root in get_settings().workspace_root_allowlist:
        validation = container.local_workspace_provider.exists_and_is_directory(root)
        if validation:
            repositories.append({"id": root, "name": root.rstrip("/").split("/")[-1], "path": root})
    return repositories


@router.get("/repositories/{repository_id:path}/branches")
def list_branches(repository_id: str) -> list[dict]:
    try:
        branches = container.git_cli_provider.list_branches(repository_id)
        current = container.git_cli_provider.current_branch(repository_id)
    except Exception:  # noqa: BLE001 - non-git folders still get a usable default branch.
        branches = ["main"]
        current = "main"
    return [{"id": branch, "name": branch, "isDefault": branch == current} for branch in branches]


@router.get("/repositories/{repository_id:path}/files", response_model=list[FileNodeDto])
def get_repository_files(
    repository_id: str,
    branch: str | None = None,
    tree_service: RepositoryTreeService = Depends(get_repository_tree_service),
) -> list[FileNodeDto]:
    return get_tree(repository_id, tree_service)


@router.get("/repositories/{repository_id:path}/file-content", response_model=dict)
def get_repository_file_content(
    repository_id: str,
    path: str,
    branch: str | None = None,
    file_read_service: FileReadService = Depends(get_file_read_service),
) -> dict:
    return get_file_content(repository_id, path, file_read_service)


@router.get("/workspace/tree", response_model=list[FileNodeDto])
def get_tree(path: str, tree_service: RepositoryTreeService = Depends(get_repository_tree_service)) -> list[FileNodeDto]:
    try:
        nodes = tree_service.get_tree(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_to_dto(node) for node in nodes]


@router.get("/workspace/files", response_model=dict)
def get_file_content(
    path: str, file_path: str, file_read_service: FileReadService = Depends(get_file_read_service)
) -> dict:
    try:
        repo_file = file_read_service.read(path, file_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"path": repo_file.metadata.path, "content": repo_file.content}


def _to_dto(node) -> FileNodeDto:
    return FileNodeDto(
        id=node.id,
        name=node.name,
        path=node.path,
        type=node.type,
        status=node.status,
        children=[_to_dto(c) for c in node.children] if node.children else None,
    )
