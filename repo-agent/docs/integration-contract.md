# RepoAgent integration contract

Single source of truth for the values shared between the FastAPI backend and the
Angular frontend (and the static preview). Backend enums live in
`backend/app/models/enums.py`; the frontend must use the identical string values.

## Run statuses (`RunStatus`)

`queued` · `planning` · `running` · `waiting_for_auth` · `validating` ·
`completing` · `completed` · `failed` · `cancelled`

Terminal: `completed`, `failed`, `cancelled`. Every run reaches a terminal state.

## Plan step statuses (`PlanStepStatus`)

`pending` · `in_progress` · `completed` · `blocked` · `skipped`

## SSE event names (`StreamEventType`)

`run_started` · `plan_created` · `plan_updated` · `tool_started` ·
`tool_completed` · `tool_failed` · `observation_created` ·
`response_batch_started` · `response_delta` · `response_batch_completed` ·
`aws_reauthentication_required` · `aws_reauthenticated` · `validation_started` ·
`validation_completed` · `conversation_compacted` · `run_completed` ·
`run_failed` · `run_cancelled` · `heartbeat`

Every event payload carries the canonical monotonic `run_id` + `sequence`
(written last in the frame so payload keys can never shadow them). Clients dedup
on `sequence`. `response_delta` uses `delta_index` for its per-batch counter.

## Response batch types (`ResponseBatchType`)

`plan` · `progress` · `repository_findings` · `explanation` ·
`code_suggestion` · `code_change` · `diff` · `validation` · `warning` · `summary`

## Error codes (`AgentRunError.code`)

`WORKSPACE_ERROR` · `WORKSPACE_NOT_FOUND` · `TOOL_PERMISSION_DENIED` ·
`TOOL_TIMEOUT` · `AWS_SSO_SESSION_EXPIRED` · `BEDROCK_ACCESS_DENIED` ·
`VALIDATION_FAILED` · `RUN_FAILED` · `RUN_CRASHED` · `RUN_STALE` ·
`AGENT_DECIDED_FAIL` · `RUN_NOT_FOUND` · `CONTEXT_LIMIT_REACHED`

`retry_action`: `reconnect` · `reauthenticate` · `resume_run` · `start_new_run` · `none`

## REST surface

```
POST   /api/workspaces/validate
POST   /api/conversations
GET    /api/conversations
GET    /api/conversations/{id}
DELETE /api/conversations/{id}
POST   /api/agent-runs                      # 202, idempotent via client_request_id
GET    /api/agent-runs/by-client-request/{client_request_id}
GET    /api/agent-runs/{id}
POST   /api/agent-runs/{id}/cancel
POST   /api/agent-runs/{id}/revert
GET    /api/agent-runs/{id}/plan
GET    /api/agent-runs/{id}/response-batches
GET    /api/agent-runs/{id}/changes
GET    /api/agent-runs/{id}/validation
GET    /api/agent-runs/{id}/events?after_sequence=N   # SSE, with replay
```

## Idempotency & reconnect rules

- One click → exactly one run. Retried `POST /api/agent-runs` with the same
  `client_request_id` returns the existing run (`created=false`), never a second.
- Reconnect with `?after_sequence=N`: server replays persisted events after `N`
  then resumes live; client ignores any `sequence <= lastSequence`.
- SSE disconnection is not run failure — recover run state via
  `GET /api/agent-runs/{id}` before retrying or creating a new run.
- Backend emits `heartbeat` every `heartbeat_interval_seconds` while active.
