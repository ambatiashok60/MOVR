# Logging Reference

Standalone logging experiments. Nothing in `test-agent`, `api-agent`, or `ai-workspace`
imports this folder.

## Files

- `logger.py` — compact, searchable application logs with accurate caller locations.
- `enhanced_logger.py` — readable cards, decisions, summaries, warnings and failures.
- `example_usage.py` — reference output patterns using direct logger calls.
- `variation_gallery.py` — minimal, timeline, progress, comparison, review, audit and JSON variations.

## Important source-location rule

Business modules should call the logger directly:

```python
logger = get_logger(__name__)
logger.info("Repository scan started | task_id=%s", task_id)
```

For pretty output, build a card string and pass it directly to `logger.info(...)`:

```python
logger.info(
    card(
        "Strategy Selection",
        fields={"Strategy": "RestAssured", "Confidence": "High"},
        decision="Proceed with repository-native RestAssured tests.",
    )
)
```

`card()` only returns a string. It does not emit a log record, so the filename, line number,
and function in the record remain the actual business call site.

## Suggested levels

- `DEBUG`: bounded evidence and diagnostic detail.
- `INFO`: stage starts, decisions, progress and completion summaries.
- `WARNING`: review findings, fallback use and uncertain decisions.
- `ERROR`: failed stages and exhausted repair attempts.
- `CRITICAL`: service-wide unavailability or data-integrity risk.
