# Deploying RepoAgent on Google Cloud

Read [DEPLOYMENT.md](DEPLOYMENT.md) first. This guide maps its production
requirements to Google Cloud; it does not remove the current application's
single-instance limitations.

## Recommended target topology

| Capability | Google Cloud service |
|---|---|
| Frontend | Cloud Storage + Cloud CDN, or Firebase Hosting |
| Backend | Cloud Run initially; GKE when custom sandboxing is required |
| Container registry | Artifact Registry |
| Durable database | Cloud SQL for PostgreSQL |
| Shared event fan-out | Memorystore for Redis |
| Secrets | Secret Manager |
| Workload identity | Cloud Run service identity / Workload Identity Federation |
| Workspace | per-run clone on ephemeral disk; Filestore only for controlled shared workspaces |
| User access | Identity-Aware Proxy or Identity Platform |
| LLM | add a Vertex AI `LLMClient`, or call Bedrock with tightly scoped AWS credentials |
| Telemetry | Cloud Logging, Monitoring, Trace, and Error Reporting |

## Deployment sequence

1. Build backend and frontend images and push immutable digests to Artifact Registry.
2. Provision a dedicated service account with least privilege; grant secrets and
   model access only to the backend identity.
3. Deploy the backend as a single Cloud Run instance until Postgres and shared
   event fan-out are implemented. Configure request timeout above the maximum run
   duration and keep SSE proxy buffering disabled.
4. Deploy static frontend assets and route `/api` to the backend over HTTPS.
5. Restrict ingress through IAP/identity controls and set the exact frontend
   origin in `REPO_AGENT_CORS_ALLOW_ORIGINS`.
6. Run disposable Ask, Agent, cancellation, and SSE replay smoke tests.

## Cloud Run constraints

- In-process background work is coupled to the serving instance. Keep minimum
  instances and CPU allocation appropriate for active runs, or move execution to
  a durable worker/job architecture before relying on scale-to-zero.
- Instance-local disk is ephemeral. It is suitable only for a per-run clone that
  can be discarded; it is not the system of record.
- Multiple instances require Cloud SQL plus shared event fan-out or reliable
  run-affinity routing. Do not horizontally scale the SQLite/in-memory topology.
- Set concurrency from measured memory and active-run behavior, not HTTP request
  throughput alone; SSE and agent runs are long-lived.

## Production security

Cloud Run isolation alone does not make execution of untrusted repository code
safe. Use a dedicated per-run sandbox with a non-root identity, read-only base
filesystem, writable scratch workspace, CPU/memory/deadline limits, and denied
network egress except explicitly required provider endpoints. GKE with gVisor or
a job-oriented isolated execution tier is appropriate when that boundary cannot
be achieved in the serving container.

Never place AWS or Google credentials in the image. Prefer workload identity for
Google APIs. If Bedrock remains the provider, store a narrowly scoped,
short-lived credential mechanism in Secret Manager and plan a migration to
federated identity rather than long-lived access keys.

## Operations checklist

- Liveness points to `/api/health`; add dependency-aware readiness before HA.
- Cloud Load Balancing timeouts exceed the SSE heartbeat and maximum idle period.
- Logs include run correlation fields but exclude prompts, source, and secrets.
- Alerts cover missing terminal events, stale runs, SSE replay failures, provider
  errors, database failures, and unexpected workspace mutations.
- Cloud SQL backups and point-in-time recovery are enabled and restore-tested.
- Rollback uses the previous immutable image digest and a schema-compatible path.

See [Operations](OPERATIONS.md) and [Security](SECURITY.md) for release blockers
and incident response.
