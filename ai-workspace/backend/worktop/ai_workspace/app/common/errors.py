from fastapi import HTTPException, status

from worktop.ai_workspace.app.common.path_safety import PathEscapesWorkspaceError


def to_http_exception(exc: Exception) -> HTTPException:
    """Central place mapping domain/application exceptions to HTTP responses — routes call
    this in their except blocks instead of each route inventing its own status code mapping."""

    if isinstance(exc, PathEscapesWorkspaceError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (FileNotFoundError, KeyError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")
