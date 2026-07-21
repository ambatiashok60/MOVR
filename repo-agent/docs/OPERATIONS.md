# Operations, reliability, and incident runbook

This document defines the minimum production operating model. Current local
defaults (SQLite, in-process event bus, no auth, host execution) are intentionally
single-instance and are not production-ready.

## 1. Service objectives

Adopt objectives only after telemetry exists and a baseline is measured.
Recommended initial indicators are:

| User journey | Indicator | Initial objective |
|---|---|---|
| Start a run | valid requests accepted without server error | 99.9% over 30 days |
| Finish a run | accepted runs reach one terminal state within configured maximum | 99.5% |
| Stream progress | persisted event becomes client-visible while connected | p95 < 2 s |
| Recover stream | reconnect replays from last sequence without loss | 99.9% |
| Protect workspace | unauthorized/escaped mutation | zero tolerated |

LLM quality is measured separately from service reliability. A model deciding
not to change code is not an availability failure; a run hanging without a
terminal state is.

## 2. Required telemetry

Structured logs must carry `run_id`, `conversation_id`, event type, tool name,
duration, outcome, and a correlation/request identifier where available. Do not
log source or secrets.

Add metrics before production:

- run starts and terminal outcomes by mode/provider/error code;
- queue time and run duration histograms;
- active runs and oldest active run age;
- LLM/tool/validation latency, timeout, and failure counts;
- SSE connections, reconnects, replay count, and sequence gaps;
- watchdog warnings/failures;
- DB latency/errors and event backlog;
- workspace changes and reverts;
- token/use estimates by provider and model.

`GET /api/health` is currently a liveness endpoint. Add a separate readiness
check for database/broker dependencies before deploying multiple replicas.

## 3. Alert policy

Page immediately for suspected sandbox escape or unauthorized mutation,
credential exposure, sustained inability to create/recover runs, or widespread
missing terminal events. Create a ticket (not a page) for elevated model
rejections, isolated validation failures, or cost drift unless a budget limit is
at risk.

Every alert needs an owner, user impact statement, dashboard link, runbook link,
and a tested condition for resolution. Alert on symptoms and error-budget burn,
not raw CPU alone.

## 4. Triage sequence

1. Establish scope: environment, version, provider, affected run IDs, start time.
2. Classify: API acceptance, orchestration, LLM, tool/sandbox, persistence, SSE,
   or frontend recovery.
3. Check the authoritative run row and its last persisted event sequence.
4. Compare logs and persisted events; do not assume an SSE disconnect failed a run.
5. Contain risk before restoring capacity when workspace or credential safety is involved.
6. Record commands/actions and timestamps in the incident timeline.

## 5. Symptom runbooks

### Runs remain active without progress

- Check `last_activity_at`, last event sequence, watchdog logs, LLM timeout, and
  tool subprocess state.
- Confirm watchdog cadence and `REPO_AGENT_RUN_STALE_FAILURE_SECONDS`.
- Do not directly mark completed. Cancel/fail through the lifecycle service so a
  terminal event is persisted.
- If widespread, stop intake and roll back the last deployment.

### SSE clients miss updates

- Query the run REST endpoint and persisted events after the client's sequence.
- Check proxy buffering, idle timeout, heartbeat delivery, and sticky routing.
- With multiple replicas, confirm the request reached the owning instance or the
  shared broker is healthy.
- Preserve replay correctness; do not create a replacement run.

### Bedrock authentication fails

- Group by error code and AWS profile/role; never log tokens.
- Local SSO: complete the serialized `aws sso login` flow.
- Workload identity: verify role trust, region, model access, and clock skew.
- If the provider is degraded, pause intake or fail clearly; do not retry without
  bounds.

### Unexpected workspace changes

- Stop new Agent runs and isolate the worker.
- Capture run ID, tool events, file-change records, snapshot, and deployed SHA.
- Revert only after preserving evidence and confirming the requested scope.
- Treat path escape or unrequested command execution as a security incident.

### SQLite lock or persistence failure

- Stop concurrent writers; confirm the deployment is still single-instance.
- Preserve the DB and WAL files before repair.
- Restore from a verified backup if integrity is in doubt.
- Do not scale SQLite-backed replicas horizontally; migrate to Postgres first.

## 6. Deployment and rollback

Deploy immutable artifacts through staging, run health and Ask/Agent smoke tests
against disposable workspaces, then promote. A rollback must restore compatible
application and schema versions; persisted events are part of the compatibility
surface. Never run destructive schema changes without a tested restore path.

After deployment verify: health/readiness, one Ask run, one Agent run in a
throwaway workspace, SSE disconnect/replay, terminal outcomes, validation, and
error-rate/latency dashboards.

## 7. Backup and disaster recovery

Define and test recovery objectives before production. Back up the durable DB,
configuration, and any required workspace/snapshot store; source repositories
should remain recoverable from their system of record. Test restore quarterly
and verify run/event sequence integrity after restore. A backup that has not been
restored is not recovery evidence.

## 8. Post-incident standard

For material incidents, publish a blameless review with impact, detection,
timeline, contributing system conditions, successful/failed safeguards, and
owned actions with due dates. Add a regression test or operational control that
would have detected or prevented recurrence.
