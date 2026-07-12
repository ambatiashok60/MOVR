# Architecture, Ask mode and Agent mode

The feature separates domain, application, infrastructure and API concerns. Models propose; tools,
policies, validation, state, review and Apply remain deterministic.

```text
Angular route and facade
 -> FastAPI route
 -> ExecutionOrchestrator
 -> ChatService or AgentService
 -> context + model + bounded tools
 -> isolated staged changes
 -> validation and review store
 -> transactional Apply
```

Ask mode loads selected repository context, retrieves relevant evidence, queries the model and returns
an answer with references; it has no write authority. Agent mode iterates observe → plan → tool call →
observation → re-plan until evidence supports a patch or the run reaches a reviewable limitation.
Destructive, sensitive or low-confidence decisions remain review items rather than silent actions.
