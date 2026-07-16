# Configuration, security and operations

Key configuration covers the model, tenant integration, workspace root, validation timeout, repair
limit, confidence thresholds, usage thresholds and `BUDGET_ENFORCEMENT_MODE=review|strict`.

Production requirements:

1. Use authenticated tenant and repository authorization.
2. Keep path guards, secret redaction and restricted-file policy mandatory.
3. Use shared task/event persistence for multiple workers.
4. Run repository commands only in a controlled workspace with allowlisted commands and timeouts.
5. Emit structured logs with correlation ID, tenant-safe repository ID, job ID, stage, duration and outcome.
6. Record model usage and validation evidence without logging source code, secrets or prompts containing them.
7. Run unit, hardening, integration and golden-scenario suites in CI.

Alert on repeated schema repair, validation timeouts, patch rejection, queue age and terminal failures.
Never silently fall back to a mock model in production.
