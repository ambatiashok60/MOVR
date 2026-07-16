# Task manager, frontend and ORM portability

## Current persistence architecture

AI Workspace has a `StateStore` protocol with `set/get/list/delete`. The container selects memory, SQLite or MySQL.
SQLite uses the standard `sqlite3` driver; MySQL uses raw PyMySQL. Neither implementation is an ORM. Specialized
session/runtime/execution/plan/review stores serialize domain objects into namespaced JSON payloads.

```text
frontend facade/services
 -> routes/application services
 -> session/runtime/execution/plan/review store interfaces
 -> container-selected adapters
    -> in-memory stores
    -> SQLiteStateStore (sqlite3)
    -> MySQLStateStore (PyMySQL)
```

This is portable for simple state but weak for task claiming, relational queries, event replay, optimistic
transitions and high-concurrency workers.

## Target frontend/task/persistence graph

```text
AiWorkspaceFacade
 -> SharedTaskController
    -> AgentService.start
    -> ExecutionService.get/cancel/retry
    -> SseService.events
    -> polling reconciler

run/cancel/status/event routes
 -> TaskApplicationService
 -> TaskRepository + EventRepository + AttemptRepository
 -> Dispatcher/worker
 -> ExecutionOrchestrator/AgentService
 -> existing session/plan/review repositories
 -> ORM adapters + host unit of work
```

The execution/task lifecycle should be normalized relational state. Large plans, observations and review payloads
may remain JSON artifacts when query requirements do not justify full normalization.

## Persistence ports

```python
class ExecutionRepository(Protocol):
    def save(self, execution: ExecutionContext) -> None: ...
    def get(self, execution_id: str) -> ExecutionContext | None: ...

class TaskRepository(Protocol):
    def create(self, task: TaskRecord) -> TaskRecord: ...
    def claim(self, task_id: str, worker_id: str, lease_until: datetime) -> TaskRecord | None: ...
    def transition(self, task_id: str, expected_version: int, change: TaskTransition) -> TaskRecord: ...

class UnitOfWork(Protocol):
    tasks: TaskRepository
    events: EventRepository
    executions: ExecutionRepository
    plans: PlanRepository
    reviews: ReviewRepository
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

Application services depend on these ports. SQLAlchemy, Django ORM, SQLModel, Worktop models, raw SQL or another
database implementation remains infrastructure.

## Recommended relational boundaries

Normalize task identity/status/version, tenant/user/repository, worker lease/heartbeat, event sequence, attempts,
review decisions and Apply transaction metadata. Retain flexible JSON for versioned request/result, plan steps,
tool observations and file-change detail, with schema version columns and size/retention controls.

## ORM adapter layout

```text
domain/task_record.py                 ORM-free entity
application/ports/task_repository.py protocol
infrastructure/sqlalchemy/models.py  mapped tables
infrastructure/sqlalchemy/mappers.py domain <-> ORM
infrastructure/sqlalchemy/repos.py   repository implementations
infrastructure/sqlalchemy/uow.py     transaction/session ownership
dependencies/container.py            DI selection
migrations/                           database-owned schema evolution
```

Equivalent directories can wrap the target repository’s ORM conventions.

## Migration from current key-value stores

1. Freeze/document serialization schema versions.
2. Introduce repository ports alongside the existing `StateStore` adapters.
3. Add ORM tables and mappers without changing application DTOs.
4. Dual-read or migrate existing namespace records in a controlled migration.
5. Bind ORM repositories in the container and run contract tests.
6. Move task/event state first; migrate session/plan/review only when required.
7. Remove dual-write after reconciliation and rollback window.

## Transaction rules

- HTTP and worker operations own separate units of work.
- Commit task creation before dispatch.
- Use an outbox/event relay so committed state and SSE/queue notification cannot diverge.
- Do not keep transactions open during LLM/tool/subprocess execution.
- Apply uses its repository transaction/journal and records task outcome after filesystem success or rollback.
- Cancellation and completion use versioned conditional transitions.
- Multi-tenant queries always include tenant authorization in repository methods.

## Frontend independence

The browser depends on stable DTOs, not database models. Replacing SQLite/PyMySQL with SQLAlchemy/PostgreSQL or a
Worktop ORM changes migrations, models, mappers, repositories and DI only. It must not change Angular components,
facade/store logic, REST/SSE paths or event semantics. If the host API envelope differs, adapt it once in frontend
transport services.

## Portability verification

Run the same repository contract suite against memory, SQLite and the target ORM DB. Add integration tests for
worker claim contention, event ordering, cancellation/completion race, lease recovery, transaction rollback,
outbox delivery, tenant isolation, page refresh/resume and Apply state reconciliation.
