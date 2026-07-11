# Internal and external dependency graphs

## Internal module graph

```text
app/main.py
 -> api/routes/generation_routes.py
 -> api/routes/job_routes.py
 -> api/routes/event_routes.py

generation_routes.py
 -> schemas/generation_request.py
 -> schemas/generation_result.py
 -> services/generation_orchestrator.py

generation_orchestrator.py
 -> runtime/generation_runtime.py
 -> policy/repository_policy_service.py
 -> security/data_governance_service.py
 -> services/technology_intelligence_service.py
 -> services/source_intelligence_service.py
 -> services/inventory_service.py
 -> services/behavioral_inventory_service.py
 -> services/spec_placement_service.py
 -> services/ownership_resolution_service.py
 -> services/test_action_service.py
 -> services/flow_merge_service.py
 -> services/code_generation_service.py
 -> patching/patch_planner.py
 -> patching/scoped_patch_writer.py
 -> validation/*
 -> services/result_builder_service.py
```

## Discovery and AST subgraph

```text
inventory_service.py
 -> inventory/inventory_builder.py
 -> inventory/inventory_reader.py
 -> inventory/repository_inventory_cache.py
 -> inventory/file_fingerprint.py
 -> inventory/dependency_map.py

inventory_builder.py
 -> tools/repo_explorer_tool.py
 -> tools/file_reader_tool.py
 -> tools/search_tool.py
 -> tools/ts_ast_parser_tool.py
 -> tools/angular_parser_tool.py
 -> tools/playwright_parser_tool.py

normalized inventory + dependency map
 -> source_intelligence_service.py
 -> behavioral_inventory_service.py
 -> candidate_test_ranking_agent.py
 -> spec_placement_agent.py
 -> ownership_resolution_agent.py
 -> locator_reasoning_agent.py
```

Parsers depend on source text and schemas; they must not depend on generation agents or patch writers. Inventory
may cache parser output, but cache invalidation depends on file hash, repository revision and parser version.

## Agent and model subgraph

```text
specialized service
 -> agents/<decision>_agent.py
 -> agents/base_agent.py
 -> prompts/<decision>_prompt.py + prompts/prompt_sections.py
 -> llm/llm_client.py
 -> llm/llm_client_factory.py
 -> llm/default_llm_client.py
 -> Worktop DefaultLLMClient
```

Agents may consume schemas/inventory evidence and produce structured decisions. They must not write repository
files directly. Only patching/writer tools cross the mutation boundary.

## Mutation and validation subgraph

```text
code_generation_service.py -> schemas/code_patch.py
 -> patching/patch_planner.py
 -> policy + path guards
 -> patching/backup_manager.py
 -> patching/scoped_patch_writer.py
 -> tools/file_writer_tool.py
 -> workspace/workspace_manager.py

candidate patch
 -> validation/syntax_validator.py
 -> validation/playwright_validator.py
 -> validation/playwright_ui_quality_validator.py
 -> validation/repo_command_validator.py
 -> tools/command_runner_tool.py
 -> repair_agent.py (bounded failure only)
```

## External dependencies

| Dependency | Type | Used by | Replacement boundary |
|---|---|---|---|
| FastAPI | runtime framework | routes/application bootstrap | host router mounting |
| Pydantic/settings | contract/config | schemas and configuration | not replaced; version aligned |
| Worktop DB/tenant dependencies | platform runtime | model/repository authorization | injected host providers |
| Worktop `DefaultLLMClient` | external model gateway | LLM adapter/factory | `LLMClient` interface |
| Git/repository filesystem | external system | inventory, workspace, patching | workspace/repository provider |
| Node/TypeScript parser environment | tooling | TS/Angular/Playwright parsing | parser adapter |
| Playwright and repository package manager | target repository | validation/execution | command resolver/adapter |
| CI/container sandbox | execution infrastructure | trusted command validation | execution provider |
| Host task/event service | platform service | future jobs/SSE | task/event repository interfaces |

## Dependency rules

Routes depend inward on application services; domain schemas never import routes. Agents depend on LLM
abstractions, not platform clients. Tools do not select product intent. Validators do not mutate accepted intent.
Platform DB, tenant, task, model and audit services enter through dependency injection. Any direct import from a
domain/schema module into FastAPI, filesystem, subprocess or Worktop infrastructure is an architecture violation.
