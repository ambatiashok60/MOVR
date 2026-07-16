# Frontend/backend wiring and AST dependency graph

## End-to-end file relationship

Test Agent has no owned Angular page, so the frontend boundary begins with a host client. A Generate
action maps to the backend as follows:

```text
Host Generate component
 -> host TestAgentClient.generate(GenerationRequest)
 -> api/routes/generation_routes.py
 -> services/generation_orchestrator.py
 -> services/inventory_service.py
 -> inventory/inventory_builder.py
 -> tools/angular_parser_tool.py + tools/ts_ast_parser_tool.py + tools/playwright_parser_tool.py
 -> agents/* and services/code_generation_service.py
 -> patching/patch_planner.py -> patching/scoped_patch_writer.py
 -> validation/*
 -> services/result_builder_service.py
 -> host store/facade -> diff and review components
```

For asynchronous UI progress, the client reads `job_routes.py` and subscribes to `event_routes.py`.
The UI job model corresponds to `schemas/generation_job.py`; the final review model comes from
`schemas/generation_result.py`, `review_report.py`, `validation_result.py`, and `code_patch.py`.

## Backend module dependency direction

```text
routes -> services/orchestrator -> agents + inventory + adapters + patching + validation
agents -> prompts + schemas + llm abstractions
inventory/services/tools -> schemas
patching/validation -> policy + security + schemas
infrastructure implementations -> abstractions
```

Schemas and abstractions must not import routes or orchestration. Parsers must not write files.
Validators inspect a staged result and do not decide product intent.

## AST architecture

`ts_ast_parser_tool.py` provides TypeScript syntax-level evidence. `angular_parser_tool.py` interprets
Angular components, templates, routes and bindings. `playwright_parser_tool.py` extracts suites,
tests, locators, hooks, fixtures and imports. Their output feeds inventory and source intelligence;
agents consume normalized evidence rather than reparsing raw source in prompts.

```text
repository files
 -> language/framework parser
 -> normalized symbols, imports, routes, selectors and tests
 -> dependency_map.py + repository inventory cache
 -> behavioral/source intelligence
 -> placement, ownership, locator and reuse decisions
```

The dependency graph should carry file nodes and typed edges such as `imports`, `declaresComponent`,
`usesTemplate`, `navigatesTo`, `extendsFixture`, `callsHelper`, and `testsSource`. When a parser cannot
resolve dynamic imports, generated routes, reflection or runtime configuration, mark the edge
`unresolved` with evidence and confidence instead of guessing.

## Change rule

When adding a frontend field, trace it through host model → request schema → route → orchestration →
result schema → client adapter → store → component. When adding parser evidence, update the parser,
normalized schema, inventory/cache invalidation, consuming decision service and regression fixture.
