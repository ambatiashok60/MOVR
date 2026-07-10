from __future__ import annotations

from pathlib import Path

from app.coverage.coverage_preservation_service import CoveragePreservationService
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.code_patch import CodePatch, PatchSet


EXISTING_SPEC = """import { test, expect } from '@playwright/test';

test.describe('Employee management', () => {
  test('creates an employee', async ({ page }) => {
    await page.goto('/employees');
    await page.click('#create');
    await expect(page.locator('.toast')).toHaveText('Employee created');
  });
});
"""


def _unit_from_spec(path: str, spec: str, title: str) -> BehavioralTestUnit:
    lines = spec.splitlines()
    start = next(index for index, line in enumerate(lines, 1) if title in line)
    end = len(lines) - 1
    return BehavioralTestUnit(
        file_path=path,
        describe_title="Employee management",
        test_title=title,
        start_line=start,
        end_line=end,
        fixtures=["page"],
        page_objects=[],
        source_excerpt="\n".join(lines[start - 1 : end]),
    )


class TestCoveragePreservation:
    def test_snapshot_extracts_behavioral_signals(self) -> None:
        service = CoveragePreservationService()
        unit = _unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")

        [entry] = service.snapshot([unit])

        assert entry.coverage_key == ("e2e/employee.spec.ts", "creates an employee")
        assert entry.navigations == ["/employees"]
        assert entry.interactions == ["click"]
        assert any("toHaveText" in assertion for assertion in entry.assertions)

    def test_appended_test_reports_added_and_preserved(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        appended = EXISTING_SPEC.replace(
            "});\n});",
            "});\n\n  test('shows empty state', async ({ page }) => {\n"
            "    await page.goto('/employees?filter=none');\n"
            "    await expect(page.locator('.empty')).toBeVisible();\n"
            "  });\n});",
        )
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(appended, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[CodePatch(path="e2e/employee.spec.ts", operation="append", content="…")]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is True
        assert [entry.test_title for entry in report.added] == ["shows empty state"]
        assert [entry.test_title for entry in report.preserved] == ["creates an employee"]
        assert report.removed == []
        assert service.review_reasons(report) == []
        assert "Removed: none" in report.summary

    def test_dropped_test_is_reported_as_removed_coverage(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        replaced = EXISTING_SPEC.replace("creates an employee", "updates an employee")
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(replaced, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="replace",
                    start_line=1,
                    end_line=9,
                    content="…",
                )
            ]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is False
        assert [entry.test_title for entry in report.removed] == ["creates an employee"]
        reasons = service.review_reasons(report)
        assert any("Coverage lost" in reason for reason in reasons)

    def test_weakened_assertions_are_reported_as_modified(self, tmp_path: Path) -> None:
        service = CoveragePreservationService()
        weakened = EXISTING_SPEC.replace(
            "    await expect(page.locator('.toast')).toHaveText('Employee created');\n",
            "",
        )
        spec_path = tmp_path / "e2e" / "employee.spec.ts"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(weakened, encoding="utf-8")

        before = service.snapshot(
            [_unit_from_spec("e2e/employee.spec.ts", EXISTING_SPEC, "creates an employee")]
        )
        patches = PatchSet(
            patches=[
                CodePatch(
                    path="e2e/employee.spec.ts",
                    operation="replace",
                    start_line=4,
                    end_line=8,
                    content="…",
                )
            ]
        )
        after = service.snapshot_after_patches(str(tmp_path), patches, before)
        report = service.compare(before, after)

        assert report.coverage_preserved is False
        assert report.removed == []
        [modification] = report.modified
        assert modification.test_title == "creates an employee"
        assert any("toHaveText" in signal for signal in modification.lost_signals)
        reasons = service.review_reasons(report)
        assert any("Coverage weakened" in reason for reason in reasons)
