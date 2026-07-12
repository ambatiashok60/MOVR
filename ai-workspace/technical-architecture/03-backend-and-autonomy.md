# Backend components and autonomy loop

- `app/api/routes/ai_workspace_routes.py`: bootstrap, Ask and Agent entry points.
- `session_routes.py`, `workspace_routes.py`: sessions, repositories, branches, files and context.
- `execution_routes.py`, `sse_routes.py`: status, plans, timelines and events.
- `review_routes.py`: file decisions, review summary and Apply.
- `application/agent/agent_service.py`: discovery, evidence gate, patch and repair loop.
- `domain/agent_turn.py`: turns, tool calls, observations and file changes.
- `application/context/`: selected context, repository instructions and learned memory.
- `application/tools/`: read/search/list/test/write/diff/apply boundaries and registry.
- `application/review/`: diffs, decisions and evidence-based engineering score.
- `repository/application/isolated_workspace_service.py`: detached worktree/copy staging.
- `workspace_transaction_service.py`: lock, hash check, snapshot, journal and rollback.
- `llm/`: Worktop adapter, gateway, telemetry, structured repair and explicit mock.
- `infrastructure/`: state stores and event publisher.

Autonomy is bounded by a goal, workspace, tool permissions, iteration/time/usage limits and evidence
quality. Limits default to review outcomes rather than hiding partial work or applying unsafe changes.
