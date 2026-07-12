"""External-to-internal mapping for script/agent generation.

Keeps the route thin: the route hands over frontend inputs and gets back a
combined step list and an internal ``GenerationRequest``. Flow-step extraction
delegates to the platform DAO (external ``worktop.core_services``) and is a
best-effort — a lookup failure must not block generation, matching the legacy
controller's tolerance.
"""

from __future__ import annotations

import json
from typing import Any

from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.core_services.app.utility.custom_logger.logging import logger



class ScriptGenAdapter:
    @staticmethod
    def prepend_flow_steps(
        flow_steps: list[str] | None,
        testcase_steps: list[str] | None,
    ) -> tuple[list[str], int]:
        """Return ``(combined_steps, flow_steps_count)`` with flow steps first.

        Execution order matters: shared flow steps (login, navigation, …) must
        run before the testcase-specific steps.
        """
        flows = [
            step
            for step in (flow_steps or [])
            if isinstance(step, str) and step.strip()
        ]
        specifics = [step for step in (testcase_steps or []) if isinstance(step, str)]
        combined = [*flows, *specifics]
        return combined, len(flows)

    @staticmethod
    def to_generation_request(
        *,
        job_id: str,
        repo_path: str,
        tenant_id: int | str | None,
        testcase_id: str,
        automation_steps: list[str],
        branch: str | None = None,
        run_validation: bool = True,
        testcase_name: str | None = None,
    ) -> GenerationRequest:
        """Build the internal ``GenerationRequest`` from resolved server state."""
        return GenerationRequest(
            job_id=job_id,
            repo_path=repo_path,
            branch=branch,
            tenant_id=str(tenant_id) if tenant_id is not None else None,
            test_case_name=(testcase_name or "").strip() or testcase_id,
            steps=list(automation_steps or []),
            run_validation=run_validation,
        )

    @staticmethod
    def extract_flow_steps(db: Any, user_story_hierarchy_id: int) -> list[str]:
        """Best-effort shared flow-step lookup via the platform DAO.

        Returns ``[]`` when the DAO is unavailable (standalone deployments) or on
        any lookup/parse failure. The concrete DAO accessor lives in the Worktop
        platform; this indirection keeps the package importable and testable
        without it.
        """
        try:
            from worktop.core_services.app.dao.test_cases_generation_dao import (
                TestcasesGenerationDAO,
            )
        except Exception:
            logger.info(
                "Flow-step DAO unavailable; no flow steps prepended | hierarchy_id=%s",
                user_story_hierarchy_id,
            )
            return []

        try:
            raw = TestcasesGenerationDAO.get_flow_steps(
                db, int(user_story_hierarchy_id)
            )
            return ScriptGenAdapter._normalize_flow_steps(raw)
        except Exception:
            logger.exception(
                "Failed to load flow steps | hierarchy_id=%s",
                user_story_hierarchy_id,
            )
            return []

    @staticmethod
    def _normalize_flow_steps(raw: Any) -> list[str]:
        """Coerce a DAO flow-step payload (JSON string / list / None) to list[str]."""
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return []
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return [raw]
        if isinstance(raw, dict):
            raw = raw.get("steps", [])
        if not isinstance(raw, list):
            return []
        return [str(step).strip() for step in raw if str(step).strip()]
