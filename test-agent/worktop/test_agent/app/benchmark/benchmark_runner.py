from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from worktop.test_agent.app.schemas.benchmark import (
    BenchmarkRegression,
    BenchmarkReport,
    BenchmarkScenario,
    ScenarioOutcome,
)
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.generation_result import GenerationResult
from worktop.core_services.app.utility.custom_logger.logging import logger


GenerateFn = Callable[[GenerationRequest], GenerationResult]


class BenchmarkRunner:
    """Run golden scenarios through the generator and score the outcomes.

    Prompt, decision-logic, or policy changes are benchmarked against the same
    golden expectations every time, so an improvement in one behavior that
    silently regresses another (append accuracy, reuse, repair success,
    validation rate, latency) is caught by numbers instead of anecdotes.
    """

    def load_scenarios(self, path: str | Path) -> list[BenchmarkScenario]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [BenchmarkScenario.model_validate(item) for item in data["scenarios"]]

    def run(
        self, scenarios: list[BenchmarkScenario], generate: GenerateFn
    ) -> BenchmarkReport:
        outcomes = [self._run_scenario(scenario, generate) for scenario in scenarios]
        report = BenchmarkReport(outcomes=outcomes, metrics=self._metrics(outcomes))
        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'benchmark', 'completed', {'scenarios': len(outcomes)})
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

    def _run_scenario(
        self, scenario: BenchmarkScenario, generate: GenerateFn
    ) -> ScenarioOutcome:
        request = GenerationRequest(
            job_id=f"benchmark-{scenario.name}-{uuid.uuid4().hex[:8]}",
            repo_path=scenario.repo_path,
            test_case_name=scenario.test_case_name or scenario.name,
            steps=scenario.steps,
        )
        started_at = perf_counter()
        try:
            result = generate(request)
        except Exception as exc:
            return ScenarioOutcome(
                scenario=scenario.name,
                kind=scenario.kind,
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
                failures=["generation raised"],
                latency_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        return self._evaluate(scenario, result, latency_ms)

    def _evaluate(
        self,
        scenario: BenchmarkScenario,
        result: GenerationResult,
        latency_ms: float,
    ) -> ScenarioOutcome:
        expected = scenario.expected
        failures: list[str] = []

        decision_correct: bool | None = None
        if expected.action:
            decision_correct = expected.action in self._decisions(result)
            if not decision_correct:
                failures.append(
                    f"expected action {expected.action}, got {self._decisions(result)}"
                )

        placement_correct: bool | None = None
        if expected.target_spec:
            placement_correct = expected.target_spec in result.files_changed
            if not placement_correct:
                failures.append(
                    f"expected {expected.target_spec} in files_changed "
                    f"{result.files_changed}"
                )

        reuse_ok: bool | None = None
        if expected.reuse_signals:
            missing = [
                signal for signal in expected.reuse_signals if signal not in result.diff
            ]
            reuse_ok = not missing
            if missing:
                failures.append(f"reuse signals missing from diff: {missing}")

        validation_passed: bool | None = None
        if result.validation is not None:
            validation_passed = result.validation.passed
            if expected.validation_should_pass and not validation_passed:
                failures.append("validation failed")

        if expected.max_latency_ms is not None and latency_ms > expected.max_latency_ms:
            failures.append(
                f"latency {latency_ms}ms exceeded budget {expected.max_latency_ms}ms"
            )

        return ScenarioOutcome(
            scenario=scenario.name,
            kind=scenario.kind,
            passed=not failures,
            decision_correct=decision_correct,
            placement_correct=placement_correct,
            reuse_ok=reuse_ok,
            validation_passed=validation_passed,
            patch_applied=bool(result.files_changed),
            repair_attempted=bool(result.validation and result.validation.repair_attempted),
            latency_ms=latency_ms,
            failures=failures,
        )

    def _decisions(self, result: GenerationResult) -> list[str]:
        decisions = [trace.decision for trace in result.decision_trace if trace.decision]
        if result.manifest is not None:
            decisions.extend(entry.decision for entry in result.manifest.decisions)
        return decisions

    def _metrics(self, outcomes: list[ScenarioOutcome]) -> dict[str, float]:
        metrics: dict[str, float] = {}

        def rate(values: list[bool]) -> float:
            return round(sum(values) / len(values), 4) if values else 1.0

        for kind in ("append", "extend", "create_spec"):
            kind_outcomes = [o for o in outcomes if o.kind == kind]
            if kind_outcomes:
                metrics[f"{kind}_accuracy"] = rate([o.passed for o in kind_outcomes])

        metrics["decision_accuracy"] = rate(
            [o.decision_correct for o in outcomes if o.decision_correct is not None]
        )
        metrics["reuse_rate"] = rate(
            [o.reuse_ok for o in outcomes if o.reuse_ok is not None]
        )
        metrics["patch_success_rate"] = rate([o.patch_applied for o in outcomes])
        metrics["validation_pass_rate"] = rate(
            [o.validation_passed for o in outcomes if o.validation_passed is not None]
        )
        repaired = [o for o in outcomes if o.repair_attempted]
        if repaired:
            metrics["repair_success_rate"] = rate(
                [bool(o.validation_passed) for o in repaired]
            )
        metrics["scenario_pass_rate"] = rate([o.passed for o in outcomes])
        if outcomes:
            latencies = [o.latency_ms for o in outcomes]
            metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
            metrics["max_latency_ms"] = max(latencies)
        return metrics
