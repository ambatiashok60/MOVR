"""
Adapter between the existing Worktop Script Generator API contract and the
new Test Agent generation domain models.

Responsibilities:

- load shared automation steps from the user-story hierarchy;
- normalize shared-step storage formats;
- prepend shared flow steps to testcase-specific steps;
- construct GenerationRequest;
- map GenerationResult into the response structure expected by the route.

The adapter does not enqueue jobs and does not execute generation.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.generation_result import GenerationResult
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


class ScriptGenAdapter:
    """Translate legacy Script Generator inputs into Test Agent models."""

    @staticmethod
    def extract_flow_steps(
        db: Session,
        user_story_hierarchy_id: int | None,
    ) -> list[str]:
        """
        Load shared automation steps from the user-story hierarchy.

        This intentionally uses UserStoryHierarchyDAO. The previous
        TestcasesGenerationDAO.get_flow_steps() call is invalid because that
        method is not available in the current platform DAO.
        """
        if not user_story_hierarchy_id:
            return []

        try:
            from worktop.core_services.app.dao.user_story_hierarchy_dao import (
                UserStoryHierarchyDAO,
            )

        except Exception:
            logger.exception(
                "User-story hierarchy DAO unavailable | hierarchy_id=%s",
                user_story_hierarchy_id,
            )
            return []

        try:
            user_story = (
                UserStoryHierarchyDAO
                .get_user_story_by_user_story_hierarchy_id(
                    db,
                    int(user_story_hierarchy_id),
                )
            )

            if user_story is None:
                logger.info(
                    "No user story found for flow-step lookup | "
                    "hierarchy_id=%s",
                    user_story_hierarchy_id,
                )
                return []

            raw_steps = getattr(
                user_story,
                "shared_automation_steps",
                None,
            )

            flow_steps = ScriptGenAdapter._normalize_flow_steps(raw_steps)

            logger.info(
                "Shared flow steps loaded | hierarchy_id=%s count=%s",
                user_story_hierarchy_id,
                len(flow_steps),
            )

            return flow_steps

        except Exception:
            # Shared-step lookup is best-effort. Failure must not prevent the
            # testcase-specific generation request from being processed.
            logger.exception(
                "Failed to load shared flow steps | hierarchy_id=%s",
                user_story_hierarchy_id,
            )
            return []

    @staticmethod
    def _normalize_flow_steps(raw: Any) -> list[str]:
        """
        Convert a stored shared-steps value into list[str].

        Supported values:

        - None
        - JSON string containing a list
        - JSON string containing {"steps": [...]}
        - plain string
        - list
        - tuple
        - dictionary containing a known steps property
        """
        if raw is None:
            return []

        normalized: Any = raw

        if isinstance(normalized, str):
            normalized = normalized.strip()

            if not normalized:
                return []

            try:
                normalized = json.loads(normalized)

            except json.JSONDecodeError:
                # A non-JSON string is treated as one executable step.
                return [normalized]

        if isinstance(normalized, dict):
            for key in (
                "steps",
                "automation_steps",
                "shared_automation_steps",
                "flow_steps",
            ):
                if key in normalized:
                    normalized = normalized.get(key)
                    break
            else:
                return []

        if isinstance(normalized, tuple):
            normalized = list(normalized)

        if not isinstance(normalized, list):
            return []

        steps: list[str] = []

        for item in normalized:
            step = ScriptGenAdapter._normalize_single_step(item)

            if step:
                steps.append(step)

        return steps

    @staticmethod
    def _normalize_single_step(item: Any) -> str:
        """
        Normalize one stored flow-step entry into text.

        Dictionaries are supported because some versions store steps as:

            {"step": "..."}
            {"description": "..."}
            {"action": "..."}
        """
        if item is None:
            return ""

        if isinstance(item, str):
            return item.strip()

        if isinstance(item, dict):
            for key in (
                "step",
                "description",
                "action",
                "text",
                "name",
            ):
                value = item.get(key)

                if value is not None and str(value).strip():
                    return str(value).strip()

            return ""

        value = str(item).strip()
        return value

    @staticmethod
    def prepend_flow_steps(
        flow_steps: list[str] | None,
        testcase_steps: list[str] | None,
    ) -> tuple[list[str], int]:
        """
        Put shared login/navigation/setup steps before testcase-specific steps.

        Returns:

            combined_steps
            number_of_shared_flow_steps
        """
        normalized_flow_steps = [
            str(step).strip()
            for step in flow_steps or []
            if str(step).strip()
        ]

        normalized_testcase_steps = [
            str(step).strip()
            for step in testcase_steps or []
            if str(step).strip()
        ]

        combined_steps = [
            *normalized_flow_steps,
            *normalized_testcase_steps,
        ]

        logger.info(
            "Automation steps combined | flow_steps=%s "
            "testcase_steps=%s total=%s",
            len(normalized_flow_steps),
            len(normalized_testcase_steps),
            len(combined_steps),
        )

        return combined_steps, len(normalized_flow_steps)

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
        """
        Build the internal GenerationRequest.

        Testcase name falls back to testcase_id so the generation pipeline
        always receives a usable test-case identity.
        """
        normalized_repo_path = str(repo_path or "").strip()

        if not normalized_repo_path:
            raise ValueError("Repository path is required.")

        normalized_testcase_id = str(testcase_id or "").strip()

        if not normalized_testcase_id:
            raise ValueError("testcase_id is required.")

        normalized_steps = [
            str(step).strip()
            for step in automation_steps
            if str(step).strip()
        ]

        if not normalized_steps:
            raise ValueError(
                "At least one automation step is required for generation."
            )

        resolved_name = (
            str(testcase_name or "").strip()
            or normalized_testcase_id
        )

        return GenerationRequest(
            job_id=str(job_id),
            repo_path=normalized_repo_path,
            branch=str(branch).strip() if branch else None,
            tenant_id=(
                str(tenant_id)
                if tenant_id is not None
                else None
            ),
            test_case_name=resolved_name,
            steps=normalized_steps,
            run_validation=bool(run_validation),
        )

    @staticmethod
    def to_response_dict(
        generation_result: GenerationResult,
        flow_steps_count: int,
        automation_steps_count: int,
    ) -> dict[str, Any]:
        """
        Convert GenerationResult into the existing HTTP/SSE response format.
        """
        decision_traces: list[dict[str, Any]] = []

        raw_decision_trace = getattr(
            generation_result,
            "decision_trace",
            None,
        )

        if raw_decision_trace:
            for trace in raw_decision_trace:
                if hasattr(trace, "model_dump"):
                    decision_traces.append(
                        trace.model_dump(mode="json")
                    )
                elif isinstance(trace, dict):
                    decision_traces.append(trace)
                else:
                    decision_traces.append(
                        {"value": str(trace)}
                    )

        validation_payload: dict[str, Any] | None = None

        validation = getattr(
            generation_result,
            "validation",
            None,
        )

        if validation is not None:
            if hasattr(validation, "model_dump"):
                validation_payload = validation.model_dump(mode="json")
            elif isinstance(validation, dict):
                validation_payload = validation
            else:
                validation_payload = {
                    "value": str(validation),
                }

        files_changed = list(
            getattr(
                generation_result,
                "files_changed",
                [],
            )
            or []
        )

        return {
            "job_id": str(
                getattr(generation_result, "job_id", "")
            ),
            "files_changed": files_changed,
            "diff_summary": str(
                getattr(
                    generation_result,
                    "diff_summary",
                    "",
                )
                or ""
            ),
            "diff": str(
                getattr(generation_result, "diff", "")
                or ""
            ),
            "confidence": float(
                getattr(
                    generation_result,
                    "confidence",
                    0.0,
                )
                or 0.0
            ),
            "automation_steps_count": int(
                automation_steps_count
            ),
            "flow_steps_count": int(flow_steps_count),
            "decision_trace": decision_traces,
            "validation": validation_payload,
        }