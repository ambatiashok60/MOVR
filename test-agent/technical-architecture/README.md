# Test Agent technical architecture

This set explains how Test Agent turns repository evidence and a functional intent into safe,
reviewable Playwright changes.

1. [Getting started](01-getting-started.md)
2. [Architecture and execution flow](02-architecture-and-flow.md)
3. [Backend components](03-backend-components.md)
4. [Frontend and host wiring](04-frontend-and-host-wiring.md)
5. [API contracts, SSE and mocks](05-contracts-sse-and-mocks.md)
6. [Configuration, security and operations](06-configuration-and-operations.md)
7. [Frontend/backend wiring and AST dependency graph](07-wiring-and-ast-dependency-graph.md)
8. [Logical decisions and stage dependency DAG](08-logical-decisions-and-stage-dag.md)
9. [Detailed stage and sub-stage decision catalog](09-detailed-stage-decision-catalog.md)
10. [Decision specifications and traced execution](10-decision-specifications-and-trace.md)
11. [Component migration and integration playbook](11-component-migration-playbook.md)
12. [Internal and external dependency graphs](12-internal-external-dependency-graphs.md)
13. [Frontend and backend service dependency map](13-service-dependency-map.md)
14. [Task manager, frontend and ORM portability](14-task-frontend-persistence-portability.md)

The cross-feature worker/SSE roadmap, including final end-to-end documentation, is in
[`../../ASYNC_EXECUTION_IMPLEMENTATION_PLAN.md`](../../ASYNC_EXECUTION_IMPLEMENTATION_PLAN.md).
The canonical three-view graph and DTO/component migration specification is in
[`../../COMPONENT_MIGRATION_GRAPH_SPEC.md`](../../COMPONENT_MIGRATION_GRAPH_SPEC.md).
Shared files, assets, generated contracts and test-resource migration are covered by
[`../../SHARED_RESOURCES_MIGRATION_SPEC.md`](../../SHARED_RESOURCES_MIGRATION_SPEC.md).

The top-level `TECHNICAL_ARCHITECTURE.md` is retained as a stable entry point.

## Dependency graphs (typed node/edge views)

Three primary graphs over one typed model — see
[`dependency-graphs/`](dependency-graphs/README.md):
1. [Backend Code Graph](dependency-graphs/01-backend-code-graph.md)
2. [Cross-Layer Contract Propagation Graph](dependency-graphs/02-cross-layer-contract-graph.md)
3. [Frontend Code Graph](dependency-graphs/03-frontend-code-graph.md)
