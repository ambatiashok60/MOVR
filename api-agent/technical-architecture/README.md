# API Agent technical architecture

1. [Getting started](01-getting-started.md)
2. [Architecture and generation flows](02-architecture-and-flows.md)
3. [Backend components](03-backend-components.md)
4. [Frontend feature and Worktop wiring](04-frontend-and-wiring.md)
5. [Routes, SSE, mocks and real APIs](05-contracts-sse-mocks.md)
6. [Framework strategies and operations](06-strategies-and-operations.md)
7. [Frontend/backend wiring and dependency graph](07-wiring-and-dependency-graph.md)
8. [Logical decisions and stage dependency DAG](08-logical-decisions-and-stage-dag.md)
9. [Detailed stage and sub-stage decision catalog](09-detailed-stage-decision-catalog.md)
10. [Decision specifications and traced execution](10-decision-specifications-and-trace.md)
11. [Component migration and integration playbook](11-component-migration-playbook.md)
12. [Test Gen frontend code and logic](12-test-gen-frontend-code-and-logic.md)
13. [Internal and external dependency graphs](13-internal-external-dependency-graphs.md)
14. [Frontend and backend service dependency map](14-service-dependency-map.md)
15. [Task manager, frontend and ORM portability](15-task-frontend-persistence-portability.md)
16. [Integration: persistence, ORM, and cross-service dependency graph](16-integration-persistence-and-dependency-graph.md)

## Dependency graphs (typed node/edge views)

Three primary graphs over one typed model — see [`dependency-graphs/`](dependency-graphs/README.md):
1. [Backend Code Graph](dependency-graphs/01-backend-code-graph.md)
2. [Cross-Layer Contract Propagation Graph](dependency-graphs/02-cross-layer-contract-graph.md)
3. [Frontend Code Graph](dependency-graphs/03-frontend-code-graph.md)

The shared worker/SSE roadmap and its final documentation phase are in
[`../../ASYNC_EXECUTION_IMPLEMENTATION_PLAN.md`](../../ASYNC_EXECUTION_IMPLEMENTATION_PLAN.md).
The canonical three-view graph and DTO/component migration specification is in
[`../../COMPONENT_MIGRATION_GRAPH_SPEC.md`](../../COMPONENT_MIGRATION_GRAPH_SPEC.md).
Shared files, assets, generated contracts and test-resource migration are covered by
[`../../SHARED_RESOURCES_MIGRATION_SPEC.md`](../../SHARED_RESOURCES_MIGRATION_SPEC.md).
