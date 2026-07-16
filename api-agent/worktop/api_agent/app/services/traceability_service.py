from __future__ import annotations

import logging
import re
from pathlib import Path

from worktop.api_agent.app.schemas.api_scenario import ApiScenario
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
)
from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.schemas.traceability import (
    RequirementTrace,
    TraceabilityMatrix,
)
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_STOPWORDS = {
    "the", "and", "with", "that", "this", "then", "for", "from", "into",
    "should", "must", "will", "when", "after", "before", "verify", "check",
    "ensure", "user", "test", "are", "is", "was", "has", "have", "been",
    "can", "not", "all", "any", "its", "api",
}
_MIN_MATCH_SCORE = 0.5


class TraceabilityService:
    """Requirement traceability: story requirement → scenario → code.

    At the story level every acceptance criterion must map to a scenario; at
    the code level every scenario step and assertion must map to generated
    code. Requirements that trace to nothing surface as `missing` instead of
    disappearing silently.
    """

    def trace_scenarios(
        self,
        request: GenerateApiScenariosRequest,
        scenarios: list[ApiScenario],
    ) -> TraceabilityMatrix:
        candidates = [
            (
                scenario.api_scenario_id,
                " ".join(
                    [
                        scenario.scenario_name,
                        *scenario.scenario_steps,
                        *scenario.assertions,
                    ]
                ),
            )
            for scenario in scenarios
        ]
        requirements = [
            (criterion, "criterion") for criterion in request.acceptance_criteria
        ]
        return self._build(requirements, candidates, source="scenario")

    def trace_code(
        self,
        request: GenerateApiTestCodeRequest,
        generated_files: list[GeneratedFile],
    ) -> TraceabilityMatrix:
        root = Path(request.repo_path)
        candidates: list[tuple[str, str]] = []
        for file in generated_files:
            target = root / file.path
            if target.is_file():
                candidates.append(
                    (file.path, target.read_text(encoding="utf-8", errors="ignore"))
                )
        requirements = [
            *((step, "step") for step in request.scenario_steps),
            *((assertion, "assertion") for assertion in request.assertions),
        ]
        return self._build(requirements, candidates, source="generated_file")

    def review_reasons(self, matrix: TraceabilityMatrix) -> list[str]:
        return [
            f"Requirement not traceable to any {trace.kind} coverage: "
            f"'{trace.requirement}'."
            for trace in matrix.requirements
            if trace.status == "missing"
        ]

    def _build(
        self,
        requirements: list[tuple[str, str]],
        candidates: list[tuple[str, str]],
        *,
        source: str,
    ) -> TraceabilityMatrix:
        traces: list[RequirementTrace] = []
        for requirement, kind in requirements:
            requirement_text = requirement.strip()
            if not requirement_text:
                continue
            traces.append(
                self._trace_requirement(requirement_text, kind, candidates, source)
            )
        missing = [trace for trace in traces if trace.status == "missing"]
        matrix = TraceabilityMatrix(
            requirements=traces,
            covered=len(traces) - len(missing),
            missing=len(missing),
            complete=not missing,
            summary=[
                f"{trace.status.upper()}: {trace.requirement}"
                + (f" → {trace.covered_by}" if trace.covered_by else "")
                for trace in traces
            ],
        )
        logger.log(
            logging.WARNING if missing else logging.INFO,
            "Requirement traceability %s: %s covered, %s missing.",
            "INCOMPLETE" if missing else "complete",
            matrix.covered,
            matrix.missing,
        )
        return matrix

    def _trace_requirement(
        self,
        requirement: str,
        kind: str,
        candidates: list[tuple[str, str]],
        source: str,
    ) -> RequirementTrace:
        best_score, best_location, best_evidence = 0.0, None, ""
        for location, text in candidates:
            score, evidence = self._match(requirement, text)
            if score > best_score:
                best_score, best_location, best_evidence = score, location, evidence

        covered = best_score >= _MIN_MATCH_SCORE and best_location is not None
        return RequirementTrace(
            requirement=requirement,
            kind=kind,  # type: ignore[arg-type]
            status="covered" if covered else "missing",
            source=source if covered else None,  # type: ignore[arg-type]
            covered_by=best_location if covered else None,
            evidence=best_evidence if covered else "",
            match_score=round(best_score, 3),
        )

    def _match(self, requirement: str, text: str) -> tuple[float, str]:
        tokens = self._tokens(requirement)
        if not tokens or not text:
            return 0.0, ""
        matched = tokens & self._tokens(text)
        if not matched:
            return 0.0, ""
        evidence = max(
            text.splitlines(),
            key=lambda line: len(matched & self._tokens(line)),
            default="",
        ).strip()
        return len(matched) / len(tokens), evidence

    def _tokens(self, text: str) -> set[str]:
        return {
            token.lower()
            for token in _TOKEN_PATTERN.findall(text)
            if len(token) > 2 and token.lower() not in _STOPWORDS
        }
