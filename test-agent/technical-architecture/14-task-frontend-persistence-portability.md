# Task manager, frontend and ORM portability

## Current reality

Test Agent generation is synchronous. `job_routes.py` returns `unknown`, `event_routes.py` emits only a heartbeat,
and there is no persistent task manager or ORM model. The Functional frontend mock therefore cannot yet depend on
a real job lifecycle.

## Target runtime dependency graph

```text
FunctionalTestGenerationFacade
 -> TestAgentTaskClient
    -> POST /api/playwright/tasks
    -> POST /api/playwright/tasks/{id}/cancel
    -> GET  /api/playwright/tasks/{id}
 -> TestAgentEventsClient
    -> GET /api/playwright/tasks/{id}/events
 -> polling/SSE reconciler

routes -> TaskApplicationService -> TaskRepository + EventRepository + Dispatcher
dispatcher -> TestAgentTaskHandler -> GenerationOrchestrator
handler -> CancellationToken + EventPublisher + repository workspace
TaskRepository/EventRepository -> ORM adapter -> host database
```

## Persistence interfaces to migrate

```python
class TaskRepository(Protocol):
    def create(self, task: TaskRecord) -> None: ...
    def get(self, task_id: str) -> TaskRecord | None: ...
    def transition(self, task_id: str, expected_version: int, status: str, **changes) -> TaskRecord: ...
    def request_cancel(self, task_id: str, actor_id: str) -> TaskRecord: ...

class EventRepository(Protocol):
    def append(self, event: TaskEvent) -> TaskEvent: ...
    def read_after(self, task_id: str, sequence: int, limit: int) -> list[TaskEvent]: ...
```

The orchestrator must not import SQLAlchemy, Django models, PyMySQL or database sessions. Only an infrastructure
adapter implements these protocols.

## Minimum relational model

`tasks`: ID, tenant/user/repository, type, idempotency key, status/stage, request/result/error JSON, cancel flag,
version, worker lease/heartbeat, timestamps. `task_events`: task ID, monotonic sequence, type/stage/status, payload,
timestamp. Add unique `(task_id, sequence)` and idempotency indexes plus tenant/repository query indexes.

## ORM replacement recipe

1. Keep domain `TaskRecord` and `TaskEvent` independent of ORM base classes.
2. Implement mappers `orm_to_domain` and `domain_to_orm` in the adapter.
3. Implement repository protocols using the host session/unit of work.
4. Create sessions inside each request/worker; never pass request sessions into worker threads.
5. Use compare-and-set on `version` for state transitions and cancellation races.
6. Register the adapter through FastAPI/Worktop dependency injection.
7. Run repository contract tests against memory and the target ORM/database.

Frontend code changes only if the public DTO/envelope changes; ORM replacement must not affect components, facade,
SSE client or task controller.
