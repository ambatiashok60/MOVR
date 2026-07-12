# AI Workspace File Reference

This is a navigation/reference guide for `ai-workspace`, the repository-aware
Chat Mode and Agent Mode workspace. It explains what each backend and frontend
area does without repeating the full code.

## Root Files

### `README.md`

Primary module overview. It explains the product goal, V1 scope, out-of-scope
items, supported repository assumptions, naming conventions, and current
integration status.

### `backend/README.md`

Backend implementation notes. This is the best place to understand the current
FastAPI architecture, verified runtime behavior, state-store choices, Ask vs
Agent execution split, correctness decisions, and open integration questions.

### `frontend/README.md`

Frontend implementation notes. It explains the Angular scaffold, file count,
real vs placeholder behavior, PrimeNG/version assumptions, SSE gap, and how the
source should be merged into the host UI project.

## Backend Project Files

### `backend/pyproject.toml`

Python project metadata for the standalone backend scaffold. Declares runtime
dependencies, optional MySQL state-store support, and development tooling.

### `backend/Dockerfile`

Container scaffold for running the backend independently during development or
integration testing.

### `backend/.gitignore`

Backend-specific ignore rules for local environment files, caches, and runtime
artifacts.

### `backend/tests/README.md`

Testing notes for the backend scaffold. Use this as the starting point when
adding route, service, state-store, path-safety, diff, and apply-flow tests.

## Backend App Entry

### `backend/worktop/ai_workspace/app/main.py`

FastAPI application bootstrap. Registers the AI Workspace route groups and
exposes health/runtime entrypoints for standalone execution.

### `backend/worktop/ai_workspace/app/__init__.py`

Package marker for the backend app.

## Backend API Routes

### `backend/worktop/ai_workspace/app/api/routes/ai_workspace_routes.py`

Top-level AI Workspace routes for Chat Mode and Agent Mode entrypoints. These
routes should stay thin and delegate execution work to application services.

### `backend/worktop/ai_workspace/app/api/routes/session_routes.py`

Session lifecycle routes. Creates, reads, lists, and resumes workspace sessions
backed by the configured state store.

### `backend/worktop/ai_workspace/app/api/routes/workspace_routes.py`

Workspace path and repository file routes. Validates local workspace paths and
serves file tree/content operations through repository services.

### `backend/worktop/ai_workspace/app/api/routes/execution_routes.py`

Execution status routes. Exposes current run state, plans, events, and other
execution-facing status data.

### `backend/worktop/ai_workspace/app/api/routes/review_routes.py`

Review/apply routes. Handles changed-file review decisions, kept/rejected file
sets, diffs, and apply requests.

### `backend/worktop/ai_workspace/app/api/routes/sse_routes.py`

Server-sent event routes. Streams execution timeline events from the event
publisher so the UI can show live progress.

### `backend/worktop/ai_workspace/app/api/routes/model_routes.py`

Model registry routes. Returns available or configured model metadata through
the model catalog service.

### `backend/worktop/ai_workspace/app/api/routes/tool_routes.py`

Tool registry routes. Returns tool metadata so the UI can explain what Agent
Mode can read, write, search, diff, or run.

## Backend Common And Config

### `backend/worktop/ai_workspace/app/config/settings.py`

Environment-backed settings for service behavior, model fallback behavior,
state backend choice, SQLite/MySQL state-store settings, and local runtime
configuration.

### `backend/worktop/ai_workspace/app/common/db.py`

Standalone database dependency placeholder. In the host Worktop backend this
should be replaced with the platform-owned DB session dependency.

### `backend/worktop/ai_workspace/app/common/tenancy.py`

Tenant resolution placeholder. In the host app this should use the existing JWT
and tenant context mechanism.

### `backend/worktop/ai_workspace/app/common/errors.py`

Shared error types and response-friendly exceptions for invalid workspace
paths, missing resources, failed execution, and unsupported operations.

### `backend/worktop/ai_workspace/app/common/path_safety.py`

Path traversal protection. Resolves requested file paths against the workspace
root and rejects reads/writes that escape the validated repository.

### `backend/worktop/ai_workspace/app/utils/logging_utils.py`

Local logging helpers used by the scaffold. During host integration these can
be mapped to the existing Worktop logger helpers.

## Backend Dependencies

### `backend/worktop/ai_workspace/app/dependencies/container.py`

Dependency container for long-lived stores and shared services. This prevents
FastAPI from creating fresh in-memory state per request.

### `backend/worktop/ai_workspace/app/dependencies/ai_workspace_dependencies.py`

Dependency factories for AI Workspace application services such as bootstrap,
session, runtime, catalog, execution, and review services.

### `backend/worktop/ai_workspace/app/dependencies/repository_dependencies.py`

Dependency factories for repository access, file reading/writing, tree
building, search, scan, and Git diff services.

### `backend/worktop/ai_workspace/app/dependencies/tool_dependencies.py`

Dependency factories for tool registry, tool selection, and concrete tool
execution services.

### `backend/worktop/ai_workspace/app/dependencies/llm_dependencies.py`

Dependency factories for the LLM gateway, application service, model-client
factory adapter, telemetry, and streaming boundaries.

## Backend Domain Models

### `backend/worktop/ai_workspace/app/ai_workspace/domain/workspace_session.py`

Domain model for a workspace session, including repository identity,
workspace path, mode state, timestamps, and conversation association.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/workspace_runtime.py`

Resolved runtime context for a session. Carries the workspace root and other
runtime details needed by repository tools and execution services.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/workspace_mode.py`

Enum for Chat/Ask Mode vs Agent Mode.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/chat_message.py`

Domain model for user, assistant, system, and tool-related conversation
messages.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/execution_context.py`

Context object passed into execution strategies. Connects prompt, selected
files, session, model choice, and runtime state.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/execution_plan.py`

Agent plan representation. Stores planned steps, reasoning, tool intentions,
and step status for display in the UI.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/execution_event.py`

Timeline event model used by the event service and SSE publisher.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/file_change.py`

Reviewable file-change model. Carries path, operation, full proposed content,
diff display data, and review status.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/review_decision.py`

Keep/reject/apply decision model for proposed file changes.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/selected_file.py`

Context-selection model for files chosen by the user or context builder.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/model_metadata.py`

Model catalog metadata shown in settings and used during model selection.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/tool_definition.py`

Tool metadata for read, write, search, diff, test, and apply capabilities.

### `backend/worktop/ai_workspace/app/ai_workspace/domain/bootstrap_state.py`

Combined initial state returned to the frontend on bootstrap.

## Backend DTOs And Mappers

### `backend/worktop/ai_workspace/app/ai_workspace/dto/base.py`

Shared DTO helpers and response base types.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/bootstrap_dto.py`

API shape for the frontend bootstrap payload.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/session_dto.py`

Request and response shapes for creating, listing, and reading workspace
sessions.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/chat_dto.py`

Request and response models for Chat/Ask Mode prompts and assistant replies.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/agent_dto.py`

Request and response models for Agent Mode runs.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/execution_dto.py`

Execution status, event, plan, and run response DTOs.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/review_dto.py`

Review and apply request/response DTOs for changed files.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/workspace_dto.py`

Workspace validation, repository tree, and file-content DTOs.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/model_dto.py`

Model registry response DTOs.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/tool_dto.py`

Tool registry response DTOs.

### `backend/worktop/ai_workspace/app/ai_workspace/dto/mappers.py`

Domain-to-DTO mapping helpers. Keeps route files from duplicating response
conversion logic.

## Backend Application Services

### `backend/worktop/ai_workspace/app/ai_workspace/application/bootstrap_service.py`

Builds the initial UI bootstrap payload: models, tools, feature flags,
permissions, preferences, and workspace defaults.

### `backend/worktop/ai_workspace/app/ai_workspace/application/workspace_path_service.py`

Validates and normalizes local workspace paths before repository services can
read or write files.

### `backend/worktop/ai_workspace/app/ai_workspace/application/workspace_runtime_service.py`

Resolves a session into a runtime object that tools and execution services can
use safely.

### `backend/worktop/ai_workspace/app/ai_workspace/application/model_catalog_service.py`

Returns model metadata for the UI. Today this is a catalog boundary around the
existing model configuration integration.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tool_catalog_service.py`

Returns tool definitions so the frontend can display available Agent Mode
capabilities.

### `backend/worktop/ai_workspace/app/ai_workspace/application/sessions/session_service.py`

Owns session creation, lookup, updates, and persistence through the configured
session store.

### `backend/worktop/ai_workspace/app/ai_workspace/application/chat/chat_service.py`

Ask Mode strategy. Builds read-only context, sends the prompt to the LLM
application service, persists the conversation result, and avoids writes.

### `backend/worktop/ai_workspace/app/ai_workspace/application/agent/agent_service.py`

Agent Mode strategy. Builds context, asks the model for plan and file changes,
stages reviewable changes, and emits execution progress.

### `backend/worktop/ai_workspace/app/ai_workspace/application/context/context_builder_service.py`

Builds repository and conversation context from selected files, recent
messages, repository scan data, and token-budget assumptions.

### `backend/worktop/ai_workspace/app/ai_workspace/application/execution/execution_orchestrator.py`

Shared execution pipeline. Creates runs, resolves runtime, selects Chat or
Agent strategy, updates status, handles failures, persists execution state, and
emits terminal events.

### `backend/worktop/ai_workspace/app/ai_workspace/application/execution/execution_event_service.py`

Creates and stores execution timeline events and forwards them to SSE
publishing.

### `backend/worktop/ai_workspace/app/ai_workspace/application/review/diff_service.py`

Creates real unified diff hunks for review display from original and proposed
file content.

### `backend/worktop/ai_workspace/app/ai_workspace/application/review/review_service.py`

Stages file changes, records keep/reject choices, resolves run-to-session
context, and applies kept changes through repository writers.

### `backend/worktop/ai_workspace/app/ai_workspace/application/prompts/prompt_builder_service.py`

Builds mode-specific prompt inputs from execution context, selected files,
repository snippets, and prior messages.

### `backend/worktop/ai_workspace/app/ai_workspace/application/prompts/prompt_renderer.py`

Renders system and user prompts for Ask Mode and Agent Mode. This is where the
structured Agent Mode JSON contract is defined.

## Backend Tools

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/base_tool.py`

Base interface for tool implementations.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/tool_registry.py`

Registry of available tools and their metadata.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/tool_selection_service.py`

Selects allowed tools based on workspace mode, permissions, and execution
context.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/tool_execution_service.py`

Central tool runner. Dispatches selected tool requests to concrete tool
implementations.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/list_files_tool.py`

Lists repository files through the repository tree service.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/read_file_tool.py`

Reads workspace files through path-safe repository access.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/write_file_tool.py`

Writes workspace files through the local file writer after path validation and
review/apply rules.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/search_repository_tool.py`

Searches repository content for symbols, text, paths, or implementation clues.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/git_diff_tool.py`

Returns Git diff information for the current workspace.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/run_test_command_tool.py`

Runs allowlisted test commands by key. It should never pass arbitrary LLM text
to a shell.

### `backend/worktop/ai_workspace/app/ai_workspace/application/tools/apply_patch_tool.py`

Applies approved file changes using the full proposed file content, not by
reconstructing files from diff snippets.

## Backend Infrastructure

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/state_store.py`

Abstract key-value state-store interface used by session, execution, review,
plan, and runtime stores.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/sqlite_state_store.py`

Default local durable state store. Good for a single backend instance and local
developer usage.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/mysql_state_store.py`

Shared state-store adapter for multi-instance host deployments.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/in_memory_session_store.py`

Session-store implementation backed by process memory or the configured state
store abstraction.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/in_memory_execution_store.py`

Execution-store implementation. Preserves run metadata needed by status,
review, and apply flows.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/in_memory_review_store.py`

Review-store implementation for staged file changes and keep/reject decisions.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/in_memory_plan_store.py`

Plan-store implementation for agent execution plans.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/in_memory_runtime_store.py`

Runtime-store implementation for resolved session runtime information.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/local_workspace_provider.py`

Local workspace provider for path-backed repositories.

### `backend/worktop/ai_workspace/app/ai_workspace/infrastructure/sse_event_publisher.py`

In-process SSE event publisher with replay/buffering behavior for frontend
timeline updates.

## Backend Repository Layer

### `backend/worktop/ai_workspace/app/repository/domain/repository_file.py`

Domain model for file content and file metadata returned from repository
access.

### `backend/worktop/ai_workspace/app/repository/domain/file_metadata.py`

Metadata for files in repository listings, including path, kind, size, and
language hints.

### `backend/worktop/ai_workspace/app/repository/domain/repository_tree.py`

Tree model for folder/file hierarchy display.

### `backend/worktop/ai_workspace/app/repository/application/repository_access_service.py`

Coordinates repository provider access and path-safe file operations.

### `backend/worktop/ai_workspace/app/repository/application/repository_scan_service.py`

Scans a repository for high-level structure and useful source/test signals.

### `backend/worktop/ai_workspace/app/repository/application/repository_tree_service.py`

Builds navigable repository tree data for the workspace file browser.

### `backend/worktop/ai_workspace/app/repository/application/file_read_service.py`

Reads file content from a validated workspace path.

### `backend/worktop/ai_workspace/app/repository/application/file_write_service.py`

Writes file content during approved apply flows.

### `backend/worktop/ai_workspace/app/repository/application/repository_search_service.py`

Searches repository files for text or code context.

### `backend/worktop/ai_workspace/app/repository/application/git_diff_service.py`

Returns Git diff information using the repository infrastructure provider.

### `backend/worktop/ai_workspace/app/repository/infrastructure/local_repository_access_provider.py`

Local filesystem provider for repository file access.

### `backend/worktop/ai_workspace/app/repository/infrastructure/local_file_writer.py`

Local filesystem writer used by apply/write flows.

### `backend/worktop/ai_workspace/app/repository/infrastructure/git_cli_provider.py`

Git command provider. Uses argument-list subprocess calls instead of shell
strings.

## Backend LLM Layer

### `backend/worktop/ai_workspace/app/llm/application/llm_client.py`

Protocol for model clients used by the AI Workspace application layer.

### `backend/worktop/ai_workspace/app/llm/application/llm_client_factory.py`

Factory boundary for creating model clients.

### `backend/worktop/ai_workspace/app/llm/application/llm_gateway.py`

Gateway that routes application requests to the selected model client.

### `backend/worktop/ai_workspace/app/llm/application/llm_application_service.py`

Application-facing LLM service. Used by Chat and Agent services instead of
calling provider clients directly.

### `backend/worktop/ai_workspace/app/llm/application/llm_stream_service.py`

Streaming boundary. Present as an integration point, but should remain honest
if the platform model client does not support streaming yet.

### `backend/worktop/ai_workspace/app/llm/application/llm_telemetry_service.py`

Captures model-call telemetry and runtime metadata.

### `backend/worktop/ai_workspace/app/llm/infrastructure/model_client_factory_adapter.py`

Adapter around the existing Worktop model-client factory pattern.

### `backend/worktop/ai_workspace/app/llm/infrastructure/default_llm_client_adapter.py`

Adapter around the existing default LLM client. This is the primary integration
point for Worktop model configuration and provider abstraction.

### `backend/worktop/ai_workspace/app/llm/infrastructure/model_client_streaming_adapter.py`

Future streaming adapter boundary for provider clients that support streaming.

### `backend/worktop/ai_workspace/app/llm/infrastructure/mock_llm_client.py`

Local mock client for explicit development-only fallback when mock LLM is
enabled.

### `backend/worktop/ai_workspace/app/integrations/existing_model_client/README.md`

Documents assumptions about the existing Worktop model client and what must be
confirmed during host backend integration.

## Frontend App Root

### `frontend/src/app/app.component.ts`

Root Angular component for the standalone scaffold.

### `frontend/src/app/app.component.html`

Root shell template that hosts routed content.

### `frontend/src/app/app.component.scss`

Root shell styles.

### `frontend/src/app/app.config.ts`

Standalone Angular provider configuration. During host integration, merge the
needed providers into the real app config instead of replacing it.

### `frontend/src/app/app.routes.ts`

Standalone route configuration. During host integration, merge the AI
Workspace route into the platform route tree.

## Frontend Layout

### `frontend/src/app/layout/main-layout/*`

Main app layout wrapper. Hosts sidebar, topbar, and routed workspace content.

### `frontend/src/app/layout/sidebar/*`

Reference sidebar navigation. In the host app this should be replaced or merged
with the real navigation configuration.

### `frontend/src/app/layout/topbar/*`

Topbar display for page title, actions, and user-level controls.

## Frontend AI Workspace Page

### `frontend/src/app/pages/ai-workspace/ai-workspace.routes.ts`

Feature route definition for the AI Workspace page.

### `frontend/src/app/pages/ai-workspace/ai-workspace.component.ts`

Container component for the AI Workspace screen. Composes the header, mode
toggle, conversation, context panel, execution timeline, review panel, settings,
and session list through the facade.

### `frontend/src/app/pages/ai-workspace/ai-workspace.component.html`

Main workspace layout template. Places the conversation and action surfaces in
a developer-oriented workspace view.

### `frontend/src/app/pages/ai-workspace/ai-workspace.component.scss`

Responsive layout styling for the workspace page.

## Frontend Models

### `frontend/src/app/pages/ai-workspace/models/ai-workspace.model.ts`

Shared feature-level UI model types.

### `frontend/src/app/pages/ai-workspace/models/bootstrap.model.ts`

Types for the backend bootstrap payload.

### `frontend/src/app/pages/ai-workspace/models/session.model.ts`

Session list, session detail, and create-session request types.

### `frontend/src/app/pages/ai-workspace/models/workspace.model.ts`

Workspace validation, repository identity, branch, file tree, and file-content
types.

### `frontend/src/app/pages/ai-workspace/models/chat-message.model.ts`

Chat and assistant message types used by the conversation UI.

### `frontend/src/app/pages/ai-workspace/models/agent-plan.model.ts`

Agent plan and step types displayed by the agent-plan component.

### `frontend/src/app/pages/ai-workspace/models/execution.model.ts`

Run status, timeline event, execution state, and progress types.

### `frontend/src/app/pages/ai-workspace/models/file-change.model.ts`

Changed-file and diff display types.

### `frontend/src/app/pages/ai-workspace/models/review.model.ts`

Review decision, apply request, and apply result types.

### `frontend/src/app/pages/ai-workspace/models/context.model.ts`

Context summary, selected files, token estimate, and context-builder types.

### `frontend/src/app/pages/ai-workspace/models/model-registry.model.ts`

Model catalog and selected-model types.

### `frontend/src/app/pages/ai-workspace/models/tool-registry.model.ts`

Tool catalog types for read/write/search/diff/test capabilities.

### `frontend/src/app/pages/ai-workspace/models/prompt.model.ts`

Prompt-library types for reusable prompts and prompt categories.

## Frontend Services

### `frontend/src/app/pages/ai-workspace/services/ai-workspace.service.ts`

Shared API-prefix and low-level feature service helpers.

### `frontend/src/app/pages/ai-workspace/services/bootstrap.service.ts`

Calls the backend bootstrap endpoint and returns initial UI state.

### `frontend/src/app/pages/ai-workspace/services/session.service.ts`

Creates, lists, reads, and updates workspace sessions.

### `frontend/src/app/pages/ai-workspace/services/workspace.service.ts`

Validates local workspace paths and loads repository file tree/content.

### `frontend/src/app/pages/ai-workspace/services/conversation.service.ts`

Sends Ask Mode/chat prompts and receives assistant responses.

### `frontend/src/app/pages/ai-workspace/services/agent.service.ts`

Starts Agent Mode runs and returns execution/review results.

### `frontend/src/app/pages/ai-workspace/services/execution.service.ts`

Loads execution status, events, plans, and timeline state.

### `frontend/src/app/pages/ai-workspace/services/review.service.ts`

Keeps, rejects, and applies proposed file changes.

### `frontend/src/app/pages/ai-workspace/services/context-builder.service.ts`

Loads and updates selected-file context and context summaries.

### `frontend/src/app/pages/ai-workspace/services/model-registry.service.ts`

Loads available model metadata.

### `frontend/src/app/pages/ai-workspace/services/tool-registry.service.ts`

Loads available Agent Mode tool metadata.

### `frontend/src/app/pages/ai-workspace/services/prompt-library.service.ts`

Loads prompt-library entries for reusable developer prompts.

### `frontend/src/app/pages/ai-workspace/services/settings.service.ts`

Persists UI preferences and workspace settings.

### `frontend/src/app/pages/ai-workspace/services/sse.service.ts`

Generic EventSource wrapper for future live execution events.

## Frontend Store And Facade

### `frontend/src/app/pages/ai-workspace/store/ai-workspace.store.ts`

Central feature state container for selected workspace, session, messages,
context, execution, review, models, tools, settings, and loading/error states.

### `frontend/src/app/pages/ai-workspace/store/ai-workspace.selectors.ts`

Derived state selectors for templates and components.

### `frontend/src/app/pages/ai-workspace/store/ai-workspace.facade.ts`

Orchestration boundary for the page. Components call the facade rather than
calling services directly.

## Frontend Components

### `frontend/src/app/pages/ai-workspace/components/workspace-header/*`

Header summary for workspace name, mode, run status, and high-level actions.

### `frontend/src/app/pages/ai-workspace/components/workspace-selector/*`

Workspace path/repository selector. Validates or selects the local repository
that the session will use.

### `frontend/src/app/pages/ai-workspace/components/mode-toggle/*`

Switches between Chat/Ask Mode and Agent Mode.

### `frontend/src/app/pages/ai-workspace/components/conversation/*`

Conversation transcript container.

### `frontend/src/app/pages/ai-workspace/components/message-bubble/*`

Individual user/assistant/system message display.

### `frontend/src/app/pages/ai-workspace/components/chat-input/*`

Prompt input and submit controls.

### `frontend/src/app/pages/ai-workspace/components/context-panel/*`

Repository tree/context panel for selecting relevant files.

### `frontend/src/app/pages/ai-workspace/components/selected-files-panel/*`

Displays files currently included in prompt context and allows removal.

### `frontend/src/app/pages/ai-workspace/components/execution-timeline/*`

Timeline/progress view for execution events.

### `frontend/src/app/pages/ai-workspace/components/agent-plan/*`

Displays Agent Mode planned steps, statuses, and reasoning.

### `frontend/src/app/pages/ai-workspace/components/review-panel/*`

Review surface for proposed file changes, keep/reject decisions, and apply
actions.

### `frontend/src/app/pages/ai-workspace/components/file-change-card/*`

Per-file changed-file summary used by the review panel.

### `frontend/src/app/pages/ai-workspace/components/diff-viewer/*`

Diff display for original vs proposed file changes.

### `frontend/src/app/pages/ai-workspace/components/prompt-library/*`

Reusable prompt picker for developer workflows.

### `frontend/src/app/pages/ai-workspace/components/ai-workspace-settings/*`

Settings panel for model, workspace, and execution preferences.

### `frontend/src/app/pages/ai-workspace/components/session-list/*`

Session history list.

### `frontend/src/app/pages/ai-workspace/components/session-card/*`

Individual session summary card.

## Frontend Shared Files

### `frontend/src/app/shared/components/code-block/*`

Reusable code block display component.

### `frontend/src/app/shared/components/loading-overlay/*`

Reusable loading overlay component.

### `frontend/src/app/shared/components/markdown-renderer/*`

Markdown display wrapper. Current scaffold uses basic rendering and should be
replaced with the host app's markdown library if one already exists.

### `frontend/src/app/shared/pipes/file-icon.pipe.ts`

Maps file names/extensions to display icons.

### `frontend/src/app/shared/pipes/status-label.pipe.ts`

Maps execution status values to readable UI labels.

### `frontend/src/app/shared/pipes/time-ago.pipe.ts`

Formats timestamps for session and event recency.

### `frontend/src/app/shared/utils/date-time.util.ts`

Date/time formatting helpers.

### `frontend/src/app/shared/utils/file-size.util.ts`

File-size formatting helpers.

### `frontend/src/app/shared/utils/string.util.ts`

String utility helpers used by display components.

### `frontend/src/app/shared/utils/token.util.ts`

Token-count display and estimation helpers.

## Current Integration Notes

The backend and frontend are aligned around `/api/ai-workspace/...` style
endpoints and a path-first local workspace flow. For production use inside the
existing Worktop app, the main integration tasks are:

- Replace standalone DB and tenancy dependencies with platform dependencies.
- Confirm the real Worktop model-client import path and method contract.
- Keep the adapter/factory model-client boundary; do not instantiate providers
  directly from Chat or Agent services.
- Wire SSE into the frontend facade once the final event contract is accepted.
- Merge Angular routes/config/layout into the host app instead of replacing
  existing app-level files.
- Use shared state such as MySQL when multiple backend instances must share
  sessions, reviews, and execution state.

