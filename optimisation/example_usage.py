from __future__ import annotations

from time import perf_counter

from enhanced_logger import card, compact_event, failure_card, summary_card
from logger import get_logger

logger = get_logger(__name__)


def generate_api_test(task_id: str, repository: str) -> None:
    started = perf_counter()

    # Crisp one-line events work well for frequent progress and log searches.
    logger.info(compact_event(
        "api_generation_started",
        task_id=task_id,
        repository=repository,
        stage="repository_discovery",
    ))

    # Cards are reserved for decisions and major stage boundaries.
    logger.info(card(
        "API Test Strategy Selection",
        status="DECIDED",
        fields={
            "Task": task_id,
            "Repository": repository,
            "Framework": "Spring Boot",
            "Strategy": "RestAssured",
            "Confidence": "High",
        },
        decision="Generate a repository-native RestAssured integration test.",
        reasoning="Existing tests and build dependencies both use RestAssured.",
        details=[
            "Reuse AuthTestHelper.",
            "Stub EmployeeClient with WireMock.",
            "Validate using ./gradlew test.",
        ],
    ))

    logger.info(summary_card(
        "API Test Generation",
        outcome="Generated and validated",
        metrics={"Files changed": 2, "Repair attempts": 0, "Review findings": 0},
        findings=["Coverage preserved", "All scenario assertions traceable"],
        duration_seconds=perf_counter() - started,
    ))


def show_failure(task_id: str) -> None:
    try:
        raise RuntimeError("Validation command returned exit code 1")
    except RuntimeError as exc:
        # exc_info retains the traceback; the card remains readable.
        logger.error(failure_card(
            "API Test Validation",
            error=exc,
            fields={"Task": task_id, "Command": "./gradlew test"},
            recovery="Send the compiler output to the bounded repair loop.",
        ), exc_info=True)


if __name__ == "__main__":
    generate_api_test("task-123", "/repos/soh-service")
    show_failure("task-123")
