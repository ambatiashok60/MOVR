from __future__ import annotations

from pathlib import Path

from worktop.api_agent.app.coverage.api_coverage_service import ApiCoverageService
from worktop.api_agent.app.schemas.api_scenario import ApiScenario
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
)
from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.services.scenario_value_service import ScenarioValueService
from worktop.api_agent.app.services.traceability_service import TraceabilityService

EXISTING_TEST = """import io.restassured.RestAssured;

class SohRecordsApiTest {
    @Test
    void returnsRecordsWithValidFilters() {
        given().auth().oauth2(token)
            .when().get("/api/soh-records")
            .then().statusCode(200)
            .body("records.size()", greaterThan(0));
    }
}
"""


class TestApiCoveragePreservation:
    def test_entry_extracts_api_signals(self) -> None:
        service = ApiCoverageService()

        entry = service.entry_from_source("SohRecordsApiTest.java", EXISTING_TEST)

        assert "/api/soh-records" in entry.endpoints
        assert "200" in entry.status_assertions
        assert any("records.size" in body for body in entry.body_assertions)
        assert "oauth2" in entry.auth_signals

    def test_updated_file_that_keeps_signals_is_preserved(self, tmp_path: Path) -> None:
        service = ApiCoverageService()
        test_file = tmp_path / "SohRecordsApiTest.java"
        test_file.write_text(EXISTING_TEST, encoding="utf-8")
        before = service.snapshot_files(str(tmp_path), ["SohRecordsApiTest.java"])

        extended = EXISTING_TEST.replace(
            "}\n",
            "    @Test\n    void returnsEmptyList() {\n"
            "        given().when().get(\"/api/soh-records?filter=none\")\n"
            "            .then().statusCode(200);\n    }\n}\n",
            1,
        )
        test_file.write_text(extended, encoding="utf-8")
        after = service.snapshot_files(str(tmp_path), ["SohRecordsApiTest.java"])

        report = service.compare(before, after)
        assert report.coverage_preserved is True
        [modification] = report.modified
        assert modification.lost_signals == []
        assert any("filter=none" in signal for signal in modification.gained_signals)
        assert service.review_reasons(report) == []

    def test_dropped_assertion_is_flagged_as_weakened(self, tmp_path: Path) -> None:
        service = ApiCoverageService()
        test_file = tmp_path / "SohRecordsApiTest.java"
        test_file.write_text(EXISTING_TEST, encoding="utf-8")
        before = service.snapshot_files(str(tmp_path), ["SohRecordsApiTest.java"])

        weakened = EXISTING_TEST.replace(
            '            .body("records.size()", greaterThan(0));\n', ""
        )
        test_file.write_text(weakened, encoding="utf-8")
        after = service.snapshot_files(str(tmp_path), ["SohRecordsApiTest.java"])

        report = service.compare(before, after)
        assert report.coverage_preserved is False
        [modification] = report.modified
        assert any("records.size" in signal for signal in modification.lost_signals)
        reasons = service.review_reasons(report)
        assert any("Coverage weakened" in reason for reason in reasons)

    def test_new_file_is_reported_as_added(self, tmp_path: Path) -> None:
        service = ApiCoverageService()
        before = service.snapshot_files(str(tmp_path), ["NewApiTest.java"])
        (tmp_path / "NewApiTest.java").write_text(EXISTING_TEST, encoding="utf-8")
        after = service.snapshot_files(str(tmp_path), ["NewApiTest.java"])

        report = service.compare(before, after)

        assert [entry.file_path for entry in report.added] == ["NewApiTest.java"]
        assert report.coverage_preserved is True


def _scenario(
    scenario_id: str,
    name: str,
    *,
    endpoint: str = "/api/soh-records",
    method: str = "GET",
    steps: list[str] | None = None,
    assertions: list[str] | None = None,
) -> ApiScenario:
    return ApiScenario(
        api_scenario_id=scenario_id,
        scenario_name=name,
        scenario_type="positive",
        method=method,
        endpoint=endpoint,
        reason="test",
        scenario_steps=steps if steps is not None else ["Call the endpoint"],
        assertions=assertions
        if assertions is not None
        else ["Status code 200", "Records list is not empty"],
    )


class TestScenarioValueEvaluator:
    def test_intra_batch_duplicate_is_flagged_and_consolidated(self) -> None:
        service = ScenarioValueService()
        first = _scenario("API_TC_001", "Retrieve SOH records with valid filters")
        duplicate = _scenario(
            "API_TC_002",
            "Verify SOH records retrieval again",
            steps=["Call the endpoint"],
            assertions=["Status code 200", "Records list is not empty"],
        )
        profile = RepoProfile(repo_path="")

        report = service.evaluate([first, duplicate], profile)

        by_id = {a.api_scenario_id: a for a in report.assessments}
        assert by_id["API_TC_001"].verdict == "NEW_COVERAGE"
        assert by_id["API_TC_002"].verdict == "FULL_DUPLICATE"
        assert by_id["API_TC_002"].duplicate_of == "API_TC_001"
        assert by_id["API_TC_002"].duplicate_source == "generated_scenario"
        assert report.requires_approval is True
        assert any("approval required" in r for r in service.review_reasons(report))

        kept, dropped = service.consolidate([first, duplicate], report)
        assert [s.api_scenario_id for s in kept] == ["API_TC_001"]
        assert [a.api_scenario_id for a in dropped] == ["API_TC_002"]

    def test_distinct_scenarios_are_new_coverage(self) -> None:
        service = ScenarioValueService()
        positive = _scenario("API_TC_001", "Retrieve SOH records")
        negative = _scenario(
            "API_TC_002",
            "Invalid employeeId returns 400",
            endpoint="/api/soh-records",
            steps=["Call the endpoint with an invalid employeeId"],
            assertions=["Status code 400", "Error message mentions employeeId"],
        )

        report = service.evaluate([positive, negative], RepoProfile(repo_path=""))

        verdicts = {a.api_scenario_id: a.verdict for a in report.assessments}
        assert verdicts["API_TC_002"] in ("NEW_COVERAGE", "MEANINGFUL_VARIATION")
        assert report.requires_approval is False

    def test_assertionless_scenario_is_low_value(self) -> None:
        service = ScenarioValueService()
        hollow = _scenario("API_TC_003", "Just call it", assertions=[])

        report = service.evaluate([hollow], RepoProfile(repo_path=""))

        assert report.assessments[0].verdict == "LOW_VALUE"
        assert any("low value" in r for r in service.review_reasons(report))


class TestRequirementTraceability:
    def test_acceptance_criteria_map_to_scenarios(self) -> None:
        service = TraceabilityService()
        request = GenerateApiScenariosRequest(
            user_story_hierarchy_id=1,
            repo_path="/tmp/repo",
            acceptance_criteria=[
                "Records are returned for valid filters",
                "Export quarterly payroll summary as PDF",
            ],
        )
        scenarios = [
            _scenario(
                "API_TC_001",
                "Retrieve SOH records with valid filters",
                steps=["Call endpoint with valid filters"],
                assertions=["Records returned", "Status code 200"],
            )
        ]

        matrix = service.trace_scenarios(request, scenarios)

        by_requirement = {t.requirement: t for t in matrix.requirements}
        covered = by_requirement["Records are returned for valid filters"]
        assert covered.status == "covered"
        assert covered.covered_by == "API_TC_001"
        assert covered.source == "scenario"
        missing = by_requirement["Export quarterly payroll summary as PDF"]
        assert missing.status == "missing"
        assert matrix.complete is False
        assert any("not traceable" in r for r in service.review_reasons(matrix))

    def test_scenario_steps_map_to_generated_code(self, tmp_path: Path) -> None:
        service = TraceabilityService()
        test_file = tmp_path / "src" / "test" / "SohRecordsApiTest.java"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(
            "void returnsRecords() {\n"
            "  // Step: call soh-records endpoint with valid employee filters\n"
            "  // Assert: status code 200; records field is not null\n"
            "  given().when().get(\"/api/soh-records\")\n"
            "    .then().statusCode(200).body(\"records\", notNullValue());\n"
            "}\n",
            encoding="utf-8",
        )
        request = GenerateApiTestCodeRequest(
            user_story_hierarchy_id=1,
            api_scenario_id="API_TC_001",
            scenario_name="Retrieve SOH records",
            repo_path=str(tmp_path),
            scenario_steps=["Call soh-records endpoint with valid employee filters"],
            assertions=["Status code 200", "Records field is not null"],
        )
        generated = [
            GeneratedFile(
                path="src/test/SohRecordsApiTest.java",
                test_target="ci",
                summary="generated",
            )
        ]

        matrix = service.trace_code(request, generated)

        assert matrix.complete is True
        assert all(t.covered_by == "src/test/SohRecordsApiTest.java" for t in matrix.requirements)
        assert service.review_reasons(matrix) == []
