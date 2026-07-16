# Backend components

The backend lives under `worktop/api_agent/app`.

- `api/routes/`: scenario, code, job, event and profile endpoints.
- `task_managers/`: queued/running/completed/failed/aborted jobs and event buffers.
- `runtime/` and `llm/`: tenant-aware model construction and usage-aware client.
- `agents/`: repository discovery, scenario planning, generation and repair decisions.
- `services/`: context, orchestration, strategy, mocks, files, coverage and review.
- `strategies/`: Java and Python repository-native generation implementations and registry.
- `tools/`: endpoint, OpenAPI, dependency, fixture, helper and command scanners.
- `validation/`: file guards, safe command execution and resolution of results.
- `workspace/`: repository locks, snapshots and journals.
- `security/`, `policy/`, `governance/`: protection, repository rules and review-first budgets.
- `schemas/`: external and internal Pydantic contracts.

Add a framework by implementing and registering a strategy with discovery evidence, generated-file
rules, command selection and validation—not by hard-coding framework checks in routes.
