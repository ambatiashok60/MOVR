# Backend components

The backend root is `worktop/test_agent/app`.

- `api/routes/`: synchronous generation plus job/event HTTP boundaries.
- `agents/`: focused structured decisions for intent, placement, ownership, locators, generation and repair.
- `adapters/`: technology boundary; Playwright is registered without coupling the orchestrator.
- `inventory/`: repository fingerprints, dependency maps and behavioral inventory.
- `services/`: orchestration, coverage, value, manifests, review and idempotency.
- `patching/`: patch planning, backups, scoped writes and unified diffs.
- `validation/`: syntax, Playwright quality and optional repository-command validation.
- `security/`: restricted-file classification and secret redaction.
- `governance/`: usage estimates and `review|strict` budget enforcement.
- `schemas/`: request, decision, patch, validation and result contracts.

`LLMClientFactory` constructs a tenant-aware adapter around Worktop's `DefaultLLMClient`. Model
responses are never treated as executable truth: they cross a schema boundary and then deterministic
path, policy and validation gates. New framework support belongs behind an adapter, not as branching
logic spread through the orchestrator.
