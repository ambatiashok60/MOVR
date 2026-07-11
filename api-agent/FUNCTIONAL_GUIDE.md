# API Agent — Functional Guide

## Purpose

API Agent converts a completed JIRA story into API scenarios and then generates repository-native
API tests with mocks, stubs, validation and review evidence.

## Workflow A — Story to API scenarios

```text
Selected JIRA story + acceptance criteria
→ repository/API discovery
→ endpoint and existing-test evidence
→ scenario generation
→ deterministic scenario guards
→ value/duplicate analysis
→ requirement traceability
→ repository policy
→ scenario table
```

Scenarios include ID, name, method, endpoint, type, target, priority, steps and assertions.
Scenario types include positive, negative, contract and security. Stage/Both scenarios are
downgraded to CI when stage infrastructure cannot be proven.

## Workflow B — Scenario to code

```text
Selected scenario
→ source and nearby-test context
→ dependency discovery
→ mock/stub plan and risk
→ repository-native strategy
→ guarded generation
→ isolated workspace write
→ repository-native validation
→ bounded repair
→ coverage/traceability/review
→ generated files
```

Current first-class strategies are Spring RestAssured, Spring MockMvc, FastAPI TestClient and
pytest/HTTPX. WebFlux/WebTestClient remains a future dedicated strategy.

## Mock and infrastructure behavior

- Reuse repository auth helpers, fixtures, builders and client utilities first.
- Generate safe local mocks/stubs when no helper exists.
- Detect constructor/annotation injection, FastAPI dependencies, HTTP clients, Kafka, cloud and Vault signals.
- High-risk infrastructure returns an approval-required plan before writing files.
- Approval authorizes isolated test doubles, never production infrastructure or credentials.

## Review and safety

The result reports strategy evidence, reused examples, source files, mock plan, validation,
coverage preservation, traceability, manifest, usage estimate, warnings and review reasons.
Usage thresholds are review-only by default. Path guards prevent production-source writes.

## Browser preview

The combined preview is available through `ai-workspace/frontend` at `/test-generation`. Browser
mocks reproduce queued tasks, SSE, scenarios, generated files, approval and validation without a backend.

