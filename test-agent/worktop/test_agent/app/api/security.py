"""Tenant scoping and JWT permission helpers for the generation API.

Tenant ownership is enforced in-repo from ``request.state.tenant_id`` (populated
by platform auth middleware in production) — this is the security-critical part:
job ids are correlation identifiers, not authorization tokens, so every job /
event / abort lookup must verify tenant ownership.

JWT permission enforcement is applied via a lazy hook: in production it wraps the
handler with the platform's ``JWTokenService.permission_required_async``; when
that platform module is unavailable (standalone / tests) it is a no-op, keeping
the package importable and testable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status

from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


def resolve_tenant(*, request: Request, payload_tenant_id: int | None) -> int:
    """Resolve the tenant from authenticated request context.

    Never trust a client-supplied tenant id on its own: if the payload carries
    one it must match the authenticated tenant.
    """
    authenticated = getattr(request.state, "tenant_id", None)
    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated tenant ID is unavailable",
        )
    authenticated_id = int(authenticated)
    if payload_tenant_id is not None and int(payload_tenant_id) != authenticated_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant ID mismatch with authenticated user",
        )
    return authenticated_id


def validate_job_tenant(request: Request, job: dict[str, Any]) -> None:
    """Ensure the authenticated tenant owns ``job`` (403 otherwise)."""
    authenticated = getattr(request.state, "tenant_id", None)
    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated tenant is unavailable",
        )
    if int(authenticated) != int(job["tenant_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Job does not belong to authenticated tenant",
        )


def resolve_user_name(request: Request) -> str:
    """Best-effort authenticated user name for audit context."""
    try:
        from worktop.admin_services.app.services.jw_token_service import (
            JWTokenService,
        )
    except Exception:
        return "System"
    try:
        user_info = JWTokenService.get_user_name_from_request(request) or {}
        return user_info.get("user_name", "System")
    except Exception:
        logger.debug("Could not resolve user name from request")
        return "System"


def require_permission(feature: str, action: str) -> Callable[[Callable], Callable]:
    """Lazy JWT permission decorator.

    In production, wraps the handler with the platform permission check. When the
    platform auth stack is unavailable it returns the handler unchanged so the
    module still imports and unit tests still run. Tenant ownership checks in the
    handlers remain the in-repo enforcement floor regardless.
    """

    def decorator(func: Callable) -> Callable:
        try:
            from worktop.admin_services.app.services.jw_token_service import (
                JWTokenService,
            )
            from worktop.utility.common_utils import CommonUtils

            features = CommonUtils.read_features_from_file()
            permission = features.get(feature, feature)
            return JWTokenService.permission_required_async(permission, action)(func)
        except Exception:
            logger.info(
                "Platform JWT permission stack unavailable; "
                "route relies on tenant-ownership enforcement | feature=%s",
                feature,
            )
            return func

    return decorator
