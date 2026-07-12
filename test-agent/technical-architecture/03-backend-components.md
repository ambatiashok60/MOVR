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

`LLMClientFactory` constructs a tenant-aware adapter that loads Worktop model configuration and calls
Worktop's `ModelClientFactory` directly. The returned provider client owns input preparation and completion
execution. The higher-level Worktop `DefaultLLMClient` is intentionally not part of this dependency path.
Model responses are never treated as executable truth: they cross a schema boundary and then deterministic
path, policy and validation gates. New framework support belongs behind an adapter, not as branching
logic spread through the orchestrator.

Every application module imports Worktop's `custom_logger.logging.logger`
directly, allowing all agent, route and orchestration records to use the
platform's consolidated console and sinks. Production therefore treats the
custom logger as a required host dependency. Standalone tests supply a
test-only stub; application modules never configure handlers themselves.
