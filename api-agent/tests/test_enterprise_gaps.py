from __future__ import annotations

from pathlib import Path

from worktop.api_agent.app.coverage.api_coverage_service import ApiCoverageService

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
