# Getting started

## Purpose

Test Agent generates repository-native Playwright functional tests. It discovers existing test
conventions, converts an intent into a placement and action plan, creates a guarded patch, validates
the result, and returns evidence for human review.

## Runtime

- Python 3.11 or newer
- FastAPI 0.111 or newer
- Pydantic 2.7 or newer
- pydantic-settings 2.2 or newer
- pytest 8 or newer
- A trusted repository workspace containing Playwright, when execution validation is enabled

## First local verification

```bash
cd test-agent
python -m pytest
```

The standalone application needs a workspace root and model configuration. In Worktop, inject the
platform DB session, authenticated tenant, repository selection, and `DefaultLLMClient`; do not use
request-provided tenant identity.

## First integration sequence

1. Mount the router under `/api/playwright`.
2. Replace standalone tenant and DB dependencies with host dependencies.
3. Submit a generation request containing the intent and repository context.
4. Display the returned plan/diff and validation evidence.
5. Require the host review action before applying sensitive or low-confidence changes.

Read [architecture and flow](02-architecture-and-flow.md) before changing orchestration behavior.
