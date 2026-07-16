# Memory, review, security and operations

Context has three layers: explicit user selection, repository-owned instructions, and learned session
memory. Store concise decisions, commands and conventions with provenance and freshness; never treat
memory as stronger evidence than current repository contents. Summaries reduce context size but retain
goal, constraints, explored files, decisions, failures and pending work.

Review decisions are per file/change: keep, reject or request revision. Apply reacquires the workspace
lock, verifies original hashes, journals the operation, writes atomically and can roll back. Sensitive
paths, secrets, generated binaries and oversized changes require policy handling.

Production configuration must disable mock LLM fallback, use durable state, authenticated tenancy,
isolated workspaces and shared events. Logs should carry correlation/session/execution IDs, stage,
tool name, duration and outcome while redacting prompts, source and secrets. Monitor queue age, tool
failures, iterations, context size, model usage, repair count, review rate, hash conflicts and Apply
rollback. Run backend tests and the Node 20 preview validation workflow in CI.
