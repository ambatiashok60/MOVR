from enhanced_logger import audit_card, comparison_card, json_event, minimal_card, progress_card, review_card, timeline_card
from logger import get_logger

logger = get_logger(__name__)


def show_gallery() -> None:
    logger.info(minimal_card("Repository Discovery", "Detected Spring Boot, Gradle, RestAssured and WireMock.", status="COMPLETE"))
    logger.info(timeline_card("API Test Generation Timeline", [
        ("Repository discovery", "done", "18 source files inspected"),
        ("Strategy selection", "done", "RestAssured / high confidence"),
        ("Mock planning", "done", "WireMock helper reused"),
        ("Code generation", "running", "2 files proposed"),
        ("Validation", "pending", "./gradlew test"),
    ], current="Code generation"))
    logger.info(progress_card("Scenario Generation", completed=7, total=10, fields={"Current stage": "Requirement traceability", "Task": "task-123"}))
    logger.info(comparison_card("Coverage Comparison", [
        ("Endpoints", 3, 4), ("Status assertions", 5, 8),
        ("Security scenarios", 1, 2), ("Lost behavior", 0, 0),
    ]))
    logger.warning(review_card("Generation Review",
        approved=["Repository-native framework", "Coverage preserved"],
        findings=["Budget estimate exceeded by 2 LLM calls"],
        blocked=["Live Kafka connection prohibited in CI"],
    ))
    logger.info(audit_card("Generation Audit Trail", [
        {"action": "strategy_selected", "actor": "agent", "detail": "RestAssured"},
        {"action": "mock_plan_approved", "actor": "ashok", "detail": "isolated WireMock"},
        {"action": "files_written", "actor": "agent", "detail": "2 test files"},
    ]))
    logger.info(json_event("generation_completed", task_id="task-123", files_changed=2, validation_passed=True, duration_seconds=18.42))


if __name__ == "__main__":
    show_gallery()
