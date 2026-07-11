from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from worktop.api_agent.app.schemas.api_scenario_request import (
    GenerateApiScenariosRequest,
)
from worktop.api_agent.app.schemas.api_scenario_result import (
    ApiScenarioGenerationResult,
)
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
)
from worktop.api_agent.app.schemas.api_test_generation_result import (
    ApiTestGenerationResult,
)
from worktop.api_agent.app.schemas.benchmark import (
    BenchmarkCase,
    BenchmarkRegression,
    BenchmarkReport,
    CaseOutcome,
)
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

ScenarioGenerateFn = Callable[[GenerateApiScenariosRequest], ApiScenarioGenerationResult]
CodeGenerateFn = Callable[[GenerateApiTestCodeRequest], ApiTestGenerationResult]


class BenchmarkRunner:
    """Run golden cases through the generator and score the outcomes.

    Prompt, strategy, or policy changes run against the same golden
    expectations every time so a change that improves one behavior and
    silently regresses another (scenario quality, code generation success,
    validation rate, latency) is caught by numbers instead of anecdotes.
    """

    def load_cases(self, path: str | Path) -> list[BenchmarkCase]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [BenchmarkCase.model_validate(item) for item in data["cases"]]

    def run(
        self,
        cases: list[BenchmarkCase],
        *,
        generate_scenarios: ScenarioGenerateFn | None = None,
        generate_code: CodeGenerateFn | None = None,
    ) -> BenchmarkReport:
        outcomes = [
            self._run_case(case, generate_scenarios, generate_code) for case in cases
        ]
        report = BenchmarkReport(outcomes=outcomes, metrics=self._metrics(outcomes))
        logger.info("Benchmark completed: %s", report.metrics)
        return report

    def detect_regressions(
        self,
        baseline: BenchmarkReport,
        current: BenchmarkReport,
        tolerance: float = 0.0,
    ) -> list[BenchmarkRegression]:
        """Metrics that got worse than baseline (latency up, everything else down)."""
        regressions: list[BenchmarkRegression] = []
        for metric, before in baseline.metrics.items():
            after = current.metrics.get(metric)
            if after is None:
                continue
            worse = (
                after > before + tolerance
                if metric.endswith("latency_ms")
                else after < before - tolerance
            )
            if worse:
                regressions.append(
                    BenchmarkRegression(
                        metric=metric,
                        baseline=before,
                        current=after,
                        delta=round(after - before, 4),
                    )
                )
        return regressions

    def _run_case(
        self,
        case: BenchmarkCase,
        generate_scenarios: ScenarioGenerateFn | None,
        generate_code: CodeGenerateFn | None,
    ) -> CaseOutcome:
        started_at = perf_counter()
        try:
            if case.kind == "scenario_plan":
                if generate_scenarios is None:
                    raise RuntimeError("no scenario generator provided")
                result = generate_scenarios(
                    GenerateApiScenariosRequest(
                        user_story_hierarchy_id=0,
                        repo_path=case.repo_path,
                        story_title=case.story_title or case.name,
                        acceptance_criteria=case.acceptance_criteria,
                    )
                )
                failures = self._evaluate_scenarios(case, result)
            else:
                if generate_code is None:
                    raise RuntimeError("no code generator provided")
                result = generate_code(
                    GenerateApiTestCodeRequest(
                        user_story_hierarchy_id=0,
                        api_scenario_id=f"benchmark-{uuid.uuid4().hex[:8]}",
                        scenario_name=case.scenario_name or case.name,
                        scenario_steps=case.scenario_steps,
                        assertions=case.assertions,
                        repo_path=case.repo_path,
                    )
                )
                failures = self._evaluate_code(case, result)
        except Exception as exc:
            return CaseOutcome(
                case=case.name,
                kind=case.kind,
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
                failures=["generation raised"],
                latency_ms=round((perf_counter() - started_at) * 1000, 2),
            )

        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        expected = case.expected
        if expected.max_latency_ms is not None and latency_ms > expected.max_latency_ms:
            failures.append(
                f"latency {latency_ms}ms exceeded budget {expected.max_latency_ms}ms"
            )
        return CaseOutcome(
            case=case.name,
            kind=case.kind,
            passed=not failures,
            latency_ms=latency_ms,
            failures=failures,
        )

    def _evaluate_scenarios(
        self, case: BenchmarkCase, result: ApiScenarioGenerationResult
    ) -> list[str]:
        failures: list[str] = []
        expected = case.expected
        if len(result.scenarios) < expected.min_scenarios:
            failures.append(
                f"expected at least {expected.min_scenarios} scenarios, "
                f"got {len(result.scenarios)}"
            )
        produced_types = {scenario.scenario_type for scenario in result.scenarios}
        for scenario_type in expected.expected_scenario_types:
            if scenario_type not in produced_types:
                failures.append(f"expected a `{scenario_type}` scenario; none produced")
        return failures

    def _evaluate_code(
        self, case: BenchmarkCase, result: ApiTestGenerationResult
    ) -> list[str]:
        failures: list[str] = []
        expected = case.expected
        if expected.expect_generated_files and not result.generated_files:
            failures.append("expected generated files; none were produced")
        if expected.expected_strategy and result.strategy_name != expected.expected_strategy:
            failures.append(
                f"expected strategy {expected.expected_strategy}, "
                f"got {result.strategy_name}"
            )
        if (
            expected.validation_should_pass
            and result.validation is not None
            and not result.validation.passed
        ):
            failures.append("validation failed")
        return failures

    def _metrics(self, outcomes: list[CaseOutcome]) -> dict[str, float]:
        metrics: dict[str, float] = {}

        def rate(values: list[bool]) -> float:
            return round(sum(values) / len(values), 4) if values else 1.0

        for kind in ("scenario_plan", "code_generation"):
            kind_outcomes = [o for o in outcomes if o.kind == kind]
            if kind_outcomes:
                metrics[f"{kind}_accuracy"] = rate([o.passed for o in kind_outcomes])
        metrics["case_pass_rate"] = rate([o.passed for o in outcomes])
        if outcomes:
            latencies = [o.latency_ms for o in outcomes]
            metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
            metrics["max_latency_ms"] = max(latencies)
        return metrics
