# Task manager, frontend and ORM portability

## Current runtime coupling

```text
ApiTestGenerationFacade
 -> ApiTestGenerationService.start/get/abort
 -> ApiTestGenerationEventsService
 -> routes
 -> global ApiTestGenerationTaskManager
    -> in-memory dict jobs + key index + threading.Lock
    -> ThreadPoolExecutor
    -> in-memory ApiTestGenerationSseManager deque buffers
    -> GenerationOrchestrator
```

There is no SQL or ORM task persistence today. Jobs/events disappear on restart and are invisible to other API
processes. The frontend exposes Generate but does not yet call `abort()` or perform periodic polling.

## Decoupled target

```text
frontend TaskController
 -> ApiTestGenerationService (REST DTOs)
 -> ApiTestGenerationEventsService (event DTOs)

routes
 -> TaskApplicationService
    -> TaskRepository
    -> EventRepository
    -> TaskDispatcher
    -> CancellationService

worker
 -> claims TaskRepository record
 -> creates DB/model/workspace unit of work
 -> GenerationOrchestrator
 -> appends events and transitions task

repository implementations
 -> InMemory (tests/local)
 -> SQLAlchemy/Worktop ORM
 -> Django ORM or other host adapter
 -> Redis/queue adapter for dispatch/events, with SQL still authoritative if selected
```

## Required repository contracts

```python
class TaskRepository(Protocol):
    def create(self, task: TaskRecord) -> TaskRecord: ...
    def get(self, task_id: str) -> TaskRecord | None: ...
    def find_by_idempotency(self, tenant_id: str, key: str) -> TaskRecord | None: ...
    def claim(self, task_id: str, worker_id: str, lease_until: datetime) -> TaskRecord | None: ...
    def transition(self, task_id: str, from_version: int, transition: TaskTransition) -> TaskRecord: ...
    def heartbeat(self, task_id: str, worker_id: str, lease_until: datetime) -> None: ...

class EventRepository(Protocol):
    def append(self, event: NewTaskEvent) -> TaskEvent: ...
    def read_after(self, task_id: str, sequence: int, limit: int = 200) -> list[TaskEvent]: ...
```

`TaskApplicationService` owns legal transitions. ORM repositories persist them; they do not decide whether a task
may go from completed back to running.

## Relational dependency model

| Table/entity | Relationships | Purpose |
|---|---|---|
| task | tenant/user/repository; optional parent task | authoritative lifecycle/request/result |
| task_event | many-to-one task | ordered replay/audit events |
| task_attempt | many-to-one task | retry/worker/lease/error history |
| repository_lease | repository + tenant + task | exclusive mutation/execution |
| task_artifact | many-to-one task | files, diff, validation, MockStubPlan references |

Avoid embedding the full event stream in `GenerationJob.events`; return events from the event repository. JSON is
appropriate for versioned request/result payloads, while lifecycle, tenancy, sequence and lease fields should be
indexed relational columns.

## ORM/session rules

- Create one session/unit of work inside the HTTP operation and a separate one inside each worker attempt.
- Never pass `db` captured by the FastAPI request into `ThreadPoolExecutor`.
- Commit the task before dispatch; workers must never observe an uncommitted task.
- Publish SSE only after the task/event transaction commits, preferably through an outbox.
- Use optimistic versioning or conditional updates for terminal/cancel races.
- Keep network/LLM/subprocess work outside database transactions.
- Store UTC timestamps and database-generated monotonic event sequences.

## Switching to another repository ORM

Copy domain records, protocols, mappers, repository contract tests and migrations—not the current in-memory task
manager. Implement an adapter using the target repo’s ORM base, session provider, transaction decorator and naming
conventions. Then replace DI bindings. Frontend, routes, orchestrator and task handler remain unchanged.

Contract tests must verify create/get, idempotency, claim contention, legal transition, cancel race, terminal
exactly-once, event sequence/replay, lease expiry, retry attempt and tenant isolation.
