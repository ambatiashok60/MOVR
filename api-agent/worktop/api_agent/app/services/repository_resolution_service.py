"""Server-side repository and testcase resolution for the generation routes.

Mirrors how ``worktop.test_agent`` treats its public contract: the caller
submits a test case row (ids + steps) and does not know where the repository
lives — that is deployment configuration. In the platform deployment the repo
path comes from the datasource properties (``DataSourceDAO``); standalone runs
fall back to the payload value or ``settings.default_repo_path`` so the
package stays usable without the platform stack.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from worktop.api_agent.app.config import settings
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)


def resolve_repository_path(db: Any, payload_repo_path: str | None) -> str:
    """Resolve the repository path server-side, payload as standalone fallback.

    Order: platform datasource configuration (authoritative when present), then
    the client-supplied path, then ``settings.default_repo_path``. A configured
    datasource always wins so a caller can never point generation at an
    arbitrary filesystem location in the platform deployment.
    """
    configured = _configured_repository_path(db)
    if configured:
        if payload_repo_path and payload_repo_path != configured:
            logger.info(
                "Ignoring client-supplied repo path in favor of datasource "
                "configuration | payload=%s",
                payload_repo_path,
            )
        return configured
    fallback = (payload_repo_path or "").strip() or (settings.default_repo_path or "").strip()
    if not fallback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Repository path is not configured: no datasource configuration "
                "was found and the request did not carry a repo_path"
            ),
        )
    return fallback


def _configured_repository_path(db: Any) -> str | None:
    if db is None:
        return None
    try:
        from worktop.core_services.app.dao.data_source_dao import DataSourceDAO
    except Exception:
        return None
    try:
        properties = DataSourceDAO.get_latest_github_properties(db) or {}
        return (properties.get("local_repo_path") or "").strip() or None
    except Exception:
        logger.exception("Failed to load repository datasource properties")
        return None


def load_testcase_name(
    *, db: Any, user_story_hierarchy_id: int, testcase_id: str
) -> str:
    """Best-effort testcase-name lookup; a failure must not block generation."""
    if db is None:
        return ""
    try:
        from worktop.core_services.app.dao.test_cases_generation_dao import (
            TestcasesGenerationDAO,
        )
    except Exception:
        return ""
    try:
        testcase = TestcasesGenerationDAO.get_testcase_by_id(
            db, int(user_story_hierarchy_id), testcase_id
        )
        return getattr(testcase, "testcase_name", "") or ""
    except Exception:
        logger.exception(
            "Failed to load testcase name | hierarchy_id=%s testcase_id=%s",
            user_story_hierarchy_id,
            testcase_id,
        )
        return ""
