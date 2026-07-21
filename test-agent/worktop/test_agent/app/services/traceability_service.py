from __future__ import annotations

import logging
import re

from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.traceability import RequirementTrace, TraceabilityMatrix
from worktop.core_services.app.utility.custom_logger.logging import logger


_STOPWORDS = {
    "the", "and", "with", "that", "this", "then", "for", "from", "into",
    "should", "must", "will", "when", "after", "before", "verify", "check",
    "ensure", "user", "page", "test", "click", "clicks", "are", "is", "was",
    "has", "have", "been", "can", "not", "all", "any", "its",
}
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_MIN_MATCH_SCORE = 0.5


class TraceabilityService:
    """Requirement traceability matrix: story requirement → covering code.

    Every story step and expected assertion is matched against the generated
    patches and the existing flows they reuse, so a reviewer can answer "where
    is requirement N implemented?" — and unimplemented requirements surface as
    `missing` instead of disappearing silently.
    """

    def build(
        self,
        request: GenerationRequest,
        intent: FunctionalIntent | None,
        patches: PatchSet,
        existing: list[BehavioralTestUnit],
    ) -> TraceabilityMatrix:
        requirements: list[tuple[str, str]] = [
            *((step, "step") for step in request.steps),
            *(
                (assertion, "assertion")
                for assertion in (intent.assertions if intent else [])
            ),
        ]
        generated_sources = [(patch.path, patch.content) for patch in patches.patches]
        existing_sources = [
            (
                f"{unit.file_path}::{unit.test_title}",
                unit.source_excerpt or unit.behavior_summary,
            )
            for unit in existing
        ]

        traces: list[RequirementTrace] = []
        for requirement, kind in requirements:
            requirement_text = requirement.strip()
            if not requirement_text:
                continue
            traces.append(
                self._trace_requirement(requirement_text, kind, generated_sources, existing_sources)
            )

        generated_count = sum(1 for trace in traces if trace.source == "generated")
        reused_count = sum(1 for trace in traces if trace.source == "existing_flow")
        missing = [trace for trace in traces if trace.status == "missing"]
        matrix = TraceabilityMatrix(
            requirements=traces,
            covered=len(traces) - len(missing),
            generated=generated_count,
            reused=reused_count,
            missing=len(missing),
            complete=not missing,
            summary=[
                f"{trace.status.upper()}: {trace.requirement}"
                + (f" → {trace.covered_by} ({trace.source})" if trace.covered_by else "")
                for trace in traces
            ],
        )
        logger.log(logging.WARNING if missing else logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'requirement_traceability', 'incomplete' if missing else 'complete', {'requirements': len(traces), 'generated': generated_count, 'reused': reused_count, 'missing': len(missing)})
        return matrix

    def review_reasons(self, matrix: TraceabilityMatrix) -> list[str]:
        return [
            f"Requirement not traceable to any code: '{trace.requirement}'."
            for trace in matrix.requirements
            if trace.status == "missing"
        ]

    def _trace_requirement(
        self,
        requirement: str,
        kind: str,
        generated_sources: list[tuple[str, str]],
        existing_sources: list[tuple[str, str]],
    ) -> RequirementTrace:
        best_score = 0.0
        best_location: str | None = None
        best_evidence = ""
        best_source: str | None = None
        for source_name, candidates in (
            ("generated", generated_sources),
            ("existing_flow", existing_sources),
        ):
            for location, text in candidates:
                score, evidence = self._match(requirement, text)
                if score > best_score:
                    best_score = score
                    best_location = location
                    best_evidence = evidence
                    best_source = source_name

        covered = best_score >= _MIN_MATCH_SCORE and best_location is not None
        return RequirementTrace(
            requirement=requirement,
            kind=kind,  # type: ignore[arg-type]
            status="covered" if covered else "missing",
            source=best_source if covered else None,  # type: ignore[arg-type]
            covered_by=best_location if covered else None,
            evidence=best_evidence if covered else "",
            match_score=round(best_score, 3),
        )

    def _match(self, requirement: str, text: str) -> tuple[float, str]:
        """Fraction of the requirement's significant tokens found in the text,
        plus the single line containing the most of them as evidence."""
        tokens = self._tokens(requirement)
        if not tokens or not text:
            return 0.0, ""
        text_tokens = self._tokens(text)
        matched = tokens & text_tokens
        score = len(matched) / len(tokens)
        if not matched:
            return 0.0, ""
        evidence = max(
            text.splitlines(),
            key=lambda line: len(matched & self._tokens(line)),
            default="",
        ).strip()
        return score, evidence

    def _tokens(self, text: str) -> set[str]:
        return {
            token.lower()
            for token in _TOKEN_PATTERN.findall(text)
            if len(token) > 2 and token.lower() not in _STOPWORDS
        }
