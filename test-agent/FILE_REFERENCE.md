# Test Agent File Reference

This is a navigation/reference guide for `test-agent`, the repository-aware
Playwright functional test generation service. It explains what each backend
area does without repeating the full code.

## Root Files

### `README.md`

Primary product and architecture documentation for the Playwright agent. It
describes the beta scope, supported repository shapes, runtime flow, API
contracts, and repository support rules.

### `pyproject.toml`

Python project metadata and dependency declaration for the standalone
Playwright agent service.

### `.env.example`

Example environment configuration for running the service locally.

### `.gitignore`

Ignore rules for generated files, local env files, and Python artifacts.

## App Entry

### `app/main.py`

FastAPI application bootstrap. Registers generation, job, and event route
modules. Also maps unsupported repository errors into a structured `422`
response with the detected repository profile.

### `app/config.py`

Application settings used by the service. Includes the decision-confidence
thresholds `min_placement_confidence`, `min_action_confidence`,
`min_ownership_confidence`, and `min_flow_merge_confidence` that gate the
decision stages (see the README's Decision Intelligence Hardening section).

### `app/errors.py`

Domain-specific exceptions. The main one is `UnsupportedRepositoryError`, used
when the repository does not fit the beta-supported Playwright scope.

## API Routes

### `app/api/routes/generation_routes.py`

Defines the main generation endpoint:

```text
POST /api/playwright/generate
```

It accepts a `GenerationRequest` and delegates to `GenerationOrchestrator`.

### `app/api/routes/job_routes.py`

Defines the job status endpoint:

```text
GET /api/playwright/jobs/{job_id}
```

Currently returns a placeholder job shape and is ready for persistence/status
store integration.

### `app/api/routes/event_routes.py`

Defines the SSE endpoint:

```text
GET /api/playwright/events/{job_id}
```

Currently emits heartbeat events and leaves durable event streaming for a later
phase.

## Runtime And LLM

### `app/runtime/generation_runtime.py`

Builds per-generation runtime context from a request. Creates the LLM client
through `LLMClientFactory` and carries job id, tenant id, repo path, branch, DB
session, and model client.

### `app/llm/llm_client.py`

Protocol/interface for LLM clients. Defines plain completion and structured
completion methods.

### `app/llm/llm_client_factory.py`

Creates the concrete model client. It logs model-client creation and wraps
Worktop model-client failures into a generation-friendly error.

### `app/llm/default_llm_client.py`

Adapter around Worktop's `DefaultLLMClient`. Handles prompt completion,
structured JSON parsing into Pydantic models, and response text extraction.

## Orchestration

### `app/services/generation_orchestrator.py`

Main workflow coordinator. The current flow is:

```text
repo strategy detection
runtime/model client creation
technology detection
test file classification
repository inventory build
UI intelligence build
functional intent extraction
source intelligence mapping
behavioral inventory extraction
spec placement decision (bootstrap-normalized onto e2e/ when scaffolding)
test action decision (LLM ranks candidates first)
low-placement-confidence flag
reconcile action <-> placement (deterministic)
action confidence gate (deterministic, safe fallback)
existing-test context resolution (extend)
safe-extension downgrade
anchor flow context resolution (append sibling / create template)
flow merge planning (extend only, grounded in existing test)
ownership resolution (grounded in intent + source evidence)
low-confidence flags (ownership, flow merge)
locator reasoning (optional stage, fed into code generation)
code generation (existing-test / anchor / flow-plan / ownership / locators fed in)
critic review
bootstrap scaffold merge (bootstrap repos only)
patch plan guard (extension target, preserved steps, append reuse,
                  reference integrity, ownership emission, created-spec
                  structure, bootstrap scaffold)
scoped patch write
validation + repair loop
result building (needs_review + review_reasons)
```

This is the central file for understanding the full generation lifecycle. The
deterministic reconcile/gate/guard steps around the LLM decisions are documented
in the README's Decision Intelligence Hardening section. Key private methods:
`_reconcile_action_with_placement`, `_gate_action_confidence`,
`_flag_low_*_confidence`, `_resolve_existing_test_context`,
`_resolve_anchor_flow_context`, `_run_optional_stage`, and the patch-plan guard
`_patch_plan_check` (extension target, `_dropped_preserved_steps`,
`_append_reuse_check`, `_reference_integrity_check`, `_ownership_emission_check`,
`_created_spec_structure_check`, and `_bootstrap_scaffold_check`), plus
`_normalize_bootstrap_placement` for bootstrap repos.

## Agents

### `app/agents/base_agent.py`

Base class for agent wrappers. Provides common model access, structured
completion, and logging helpers.

### `app/agents/functional_intent_agent.py`

Extracts structured functional intent from the user-provided test case name and
steps.

### `app/agents/source_mapper_agent.py`

Maps functional intent to likely source files, routes, components, or UI areas.

### `app/agents/spec_placement_agent.py`

Decides where generated or updated Playwright coverage should live. Produces a
`SpecPlacementDecision`.

### `app/agents/test_action_decision_agent.py`

Decides whether to create a new test, append to an existing block, update an
existing test, or perform another test-action shape.

### `app/agents/flow_merge_agent.py`

Plans how requested steps should merge with an existing proven flow. Takes the
`ExistingTestContext` so `stable_region`/`preserved_steps` are derived from the
actual test source rather than the functional intent. Runs only for
`extend_existing_test`.

### `app/agents/ownership_resolution_agent.py`

Resolves ownership of files, specs, page objects, fixtures, and helper areas
from repository inventory. Produces a first-class decision with `create_new`
(reuse vs create a new owner), bounded confidence, and a `DecisionTrace`; the
deterministic fallback reuses an existing owner rather than inventing one.

### `app/agents/locator_reasoning_agent.py`

Determines locator approaches from source intelligence and UI evidence.
Produces an evidence-grounded `LocatorDecisionSet` that is fed into the code
generation prompt (optional stage — failure never aborts generation).

### `app/agents/code_generation_agent.py`

Model-facing code generation agent. Produces patch/code output based on
placement, action, and UI context.

### `app/agents/critic_agent.py`

Reviews generated patches before they are written. Used as a quality gate for
patch content.

### `app/agents/repair_agent.py`

Future repair path for validation failures. Intended to revise patches after
validator feedback.

### `app/agents/candidate_test_ranking_agent.py`

LLM structured-output agent that ranks candidate existing behavioral tests by
behavioral overlap with the `FunctionalIntent` (shared route, screen, journey,
assertions, fixtures, page objects), producing a `CandidateRanking`. Falls back
to deterministic passthrough (original order) with no intent, no LLM client,
one-or-fewer candidates, or on error.

## Prompts

### `app/prompts/prompt_sections.py`

Reusable prompt section helpers shared by other prompt builders:

- `response_contract()` — schema + canonical valid/invalid examples for every
  structured model (labeled per-action examples for `PatchSet`); unknown models
  get schema-only guidance, never a fabricated empty example.
- `curated_inventory()` / `curated_ui_context()` / `curated_test_units()` —
  prompt-payload curation: strips per-file hashes, caps evidence lists with
  omission markers, keeps E2E candidates first, truncates candidate excerpts
  (never the extend target's).
- `playwright_best_practices()` — the modern-Playwright scaffold injected for
  `create_new_spec`, governing when the repository has nothing to reuse.

### `app/prompts/functional_intent_prompt.py`

Prompt for extracting functional intent from natural language steps.

### `app/prompts/source_mapping_prompt.py`

Prompt for mapping functional intent to application source context.

### `app/prompts/spec_placement_prompt.py`

Prompt for deciding where the generated Playwright test should live.

### `app/prompts/test_action_prompt.py`

Prompt for deciding the test action: create, append, update, or merge.

### `app/prompts/flow_merge_prompt.py`

Prompt for merging new test flow into an existing proven flow. Instructs the
model to derive `stable_region`/`preserved_steps` from the supplied existing test
source and to explain the kept-vs-added decision in a `decision_trace`.

### `app/prompts/candidate_ranking_prompt.py`

Prompt for ranking existing tests by how well each already owns the requested
behavior. Consumed by `CandidateTestRankingAgent`.

### `app/prompts/ownership_resolution_prompt.py`

Prompt for resolving file/module ownership. Grounded in the functional intent
and the needed locators/components from source intelligence, with
reuse-vs-create standards and a required `decision_trace`.

### `app/prompts/locator_reasoning_prompt.py`

Prompt for choosing locator strategy.

### `app/prompts/code_generation_prompt.py`

Prompt for producing final code patches. Renders and enforces reuse of the
`ExistingTestContext` (extend target), `AnchorFlowContext` (append reuse base /
create style template), `FlowMergePlan` (stable/extension regions),
`OwnershipResolution` (where new locators/helpers belong), and evidence-grounded
`LocatorDecision`s (use exactly these locators). Injects the Playwright
best-practices scaffold for `create_new_spec` and forbids referencing members or
imports that do not exist in the repo or the emitted patch set.

### `app/prompts/patch_review_prompt.py`

Prompt for critic/review pass over generated patches.

## Schemas

### `app/schemas/generation_request.py`

Input request model for Playwright test generation. Carries job id, repo path,
branch, tenant id, test case name, steps, and validation preference.

### `app/schemas/generation_result.py`

Final generation response model. Contains files changed, diff summary,
confidence, decision trace, validation, repo profile, and the review signal
`needs_review` + `review_reasons` populated by the confidence gates.

### `app/schemas/generation_job.py`

Job status/result shape for the job route.

### `app/schemas/repo_profile.py`

Repository support/profile model. Captures support status, blockers, warnings,
Playwright configs, package manager, package scripts, frameworks, lockfiles,
monorepo tooling, and other repo-level signals. Includes `requires_bootstrap`
for qualifying UI repos with no E2E framework yet.

### `app/schemas/technology_profile.py`

Technology classification output for the repository.

### `app/schemas/repository_inventory.py`

Repository inventory model. Tracks discovered specs, source files, page
objects, fixtures, helpers, config files, and other repository assets.

### `app/schemas/test_file_classification.py`

Classification model for test/source/helper files.

### `app/schemas/playwright_ui_context.py`

UI intelligence model assembled from repository inventory, source evidence, and
Playwright conventions.

### `app/schemas/functional_intent.py`

Structured representation of the requested functional behavior.

### `app/schemas/source_intelligence.py`

Source mapping output. Links functional intent to likely app source, UI
components, routes, and evidence.

### `app/schemas/behavioral_test_unit.py`

Parsed existing Playwright behavior unit (test block with title, location, body,
metadata). Also defines `ExistingTestContext` (the exact edit target for an
extend) and `AnchorFlowContext` (a reference-only sibling test whose setup an
appended test should reuse — never patched).

### `app/schemas/spec_placement.py`

Spec placement decision model: target file, `create_new`, bounded confidence,
and decision trace. Includes `SpecPlacementDecisions` label constants.

### `app/schemas/test_action_decision.py`

Decision model for the test action. `action` is a `Literal` of
`extend_existing_test` / `append_new_test` / `create_new_spec` (invalid values
fail validation and route to the deterministic fallback), backed by the
`TestActions` constants, with bounded confidence.

### `app/schemas/candidate_ranking.py`

Ranking output for existing tests: `CandidateRanking` holding `RankedCandidateRef`
entries (file/title/start_line/relevance/reason). Produced by the ranking agent.

### `app/schemas/flow_merge.py`

Flow merge plan model: `stable_region`, `extension_region`, `preserved_steps`,
`added_steps`, plus bounded confidence and a `DecisionTrace` for the
kept-vs-added reasoning.

### `app/schemas/ownership_resolution.py`

Ownership resolution output for files/modules/helpers/specs. Carries `create_new`
(reuse vs create a new owner), bounded confidence, and a `DecisionTrace`.

### `app/schemas/locator_decision.py`

Locator strategy decision model.

### `app/schemas/code_patch.py`

Patch models:

```text
CodePatch
PatchSet
PatchWriteResult
```

Used by code generation and scoped patch writing.

### `app/schemas/decision_trace.py`

Decision trace model used to expose reasoning from placement/action decisions.

### `app/schemas/validation_result.py`

Validation result and check models for syntax, Playwright, repo command, and UI
quality validation.

## Services

### `app/services/repo_strategy_service.py`

Classifies whether the repository is supported, supported with warnings, or
unsupported for beta Playwright generation. A qualifying Angular/React
TypeScript UI repo with no Playwright framework at all is classified as a
bootstrap candidate (`requires_bootstrap=true`) instead of unsupported; a repo
with a Playwright config but no specs yet is a warning, not a blocker.

### `app/services/bootstrap_scaffold_service.py`

Deterministic Playwright framework scaffold for bootstrap repos: emits
`playwright.config.ts` (testDir `./e2e`, CI retries, webServer from the repo's
start/dev script), a `package.json` merge adding `@playwright/test` +
`test:e2e`, and an `e2e/fixtures.ts` entry point. Merges with LLM-generated
patches; the deterministic scaffold wins on path collision.

### `app/services/technology_intelligence_service.py`

Detects repository technology profile from repo profile and support signals.

### `app/services/test_file_classifier_service.py`

Classifies files as specs, helpers, fixtures, page objects, source, etc.

### `app/services/inventory_service.py`

Builds repository inventory using file classifications and repository scanning.

### `app/services/playwright_ui_intelligence_service.py`

Builds Playwright/UI context from repository inventory and repo profile.

### `app/services/source_intelligence_service.py`

Maps functional intent to source intelligence using the source mapper agent.

### `app/services/behavioral_inventory_service.py`

Extracts behavioral test units from existing Playwright test inventory.

### `app/services/spec_placement_service.py`

Decides where to place the generated/updated spec using the placement agent.

### `app/services/test_action_service.py`

Decides what action to take on tests. First runs the LLM ranking agent over the
behavioral candidates (using the functional intent), then the decision agent over
the ranked list, with a deterministic fallback.

### `app/services/flow_merge_service.py`

Plans how new steps should merge into the existing proven flow. Accepts the
`ExistingTestContext` so the plan is grounded in the actual test source.

### `app/services/ownership_resolution_service.py`

Resolves ownership of existing repo files and test-support structures.

### `app/services/code_generation_service.py`

Generates patch sets using the code generation agent from placement, action, UI
context, and the grounding signals: `ExistingTestContext`, `FlowMergePlan`,
`OwnershipResolution`, and `AnchorFlowContext`.

### `app/services/result_builder_service.py`

Builds the final `GenerationResult` from request, patches, patch-write result,
validation, decision traces, and repo profile. Sets `needs_review` /
`review_reasons` when the confidence gates flagged any decision.

### `app/services/staleness_service.py`

Compares repo HEAD values to decide whether cached inventory is stale.

## Inventory

### `app/inventory/inventory_builder.py`

Builds repository inventory by scanning paths and grouping files by role.

### `app/inventory/inventory_reader.py`

Convenience reader for inventory subsets such as E2E specs.

### `app/inventory/repository_inventory_cache.py`

Loads and saves repository inventory cache files.

### `app/inventory/file_fingerprint.py`

Creates file fingerprints for cache/staleness decisions.

### `app/inventory/dependency_map.py`

Simple dependency map model for source-to-target relationships.

## Tools

### `app/tools/file_reader_tool.py`

Safe file reader for repository-relative paths.

### `app/tools/file_writer_tool.py`

Safe file writer for repository-relative paths.

### `app/tools/search_tool.py`

Search helper for repository files.

### `app/tools/git_tool.py`

Git helper for HEAD/diff information.

### `app/tools/command_runner_tool.py`

Runs repository commands with timeout and captured output.

### `app/tools/playwright_parser_tool.py`

Parses Playwright specs to extract `test(...)` blocks and `describe(...)`
blocks with line ranges and behavioral metadata.

### `app/tools/angular_parser_tool.py`

Extracts Angular-specific source signals from files.

### `app/tools/ts_ast_parser_tool.py`

TypeScript AST/source parser placeholder for extracting structured TS signals.

## Patching

### `app/patching/scoped_patch_writer.py`

Applies generated patches safely. Resolves safe paths, creates backups, writes
content, and produces unified diffs.

### `app/patching/patch_planner.py`

Validates patch shape before writing.

### `app/patching/backup_manager.py`

Creates backups before file updates.

### `app/patching/diff_generator.py`

Generates unified diffs for changed files.

## Validation

### `app/validation/playwright_validator.py`

Validates Playwright test discovery and duplicate test titles.

### `app/validation/playwright_ui_quality_validator.py`

Checks Playwright/UI quality signals such as assertions and basic test
structure.

### `app/validation/repo_command_validator.py`

Runs or resolves repo-native validation commands, depending on configured
validation behavior.

### `app/validation/syntax_validator.py`

Syntax validation placeholder.

## Utilities

### `app/utils/logging_utils.py`

Builds consistent logging metadata for custom Worktop logging utilities.

## Decision Intelligence Hardening

The placement/test-action decisions are wrapped in typed contracts and
deterministic guardrails, the ranking pass is real, and the previously-discarded
flow-merge/ownership agents are wired into code generation. Full narrative and
old-vs-new comparison live in the README's Decision Intelligence Hardening
section. Files involved:

```text
schemas/test_action_decision.py     Literal action + TestActions constants
schemas/spec_placement.py           bounded confidence + labels
schemas/candidate_ranking.py        ranking schema (new)
schemas/behavioral_test_unit.py     ExistingTestContext + AnchorFlowContext
schemas/flow_merge.py               confidence + DecisionTrace
schemas/ownership_resolution.py     create_new + DecisionTrace
schemas/generation_result.py        needs_review + review_reasons
prompts/candidate_ranking_prompt.py ranking prompt (new)
prompts/flow_merge_prompt.py        grounded in existing test source
prompts/code_generation_prompt.py   anchor/flow/ownership/locator reuse rules
prompts/prompt_sections.py          playwright_best_practices scaffold
prompts/ownership_resolution_prompt.py  needed-locators grounding
agents/candidate_test_ranking_agent.py  real LLM ranking + fallback
services/generation_orchestrator.py reconcile, gates, optional stages, guards
                                    (reference integrity, ownership emission,
                                    created-spec structure, bootstrap scaffold)
services/repo_strategy_service.py   bootstrap classification
services/bootstrap_scaffold_service.py  deterministic framework scaffold (new)
schemas/repo_profile.py             requires_bootstrap flag
config.py                           min_*_confidence thresholds
```

### `tests/test_structured_output_hardening.py`

Unit tests covering the hardening: Literal/confidence validation, placement↔
action reconciliation, confidence gating, LLM ranking, anchor flow selection
(append sibling and create template), append-reuse and extend-preservation
guards, flow-merge grounding, reference-integrity (imports + page-object
members), ownership emission, created-spec structure, the best-practices
prompt scaffold, bootstrap classification, the framework scaffold service,
the bootstrap guard, per-model contract examples, context curation, and the
shallow-trace review flag.

## Current Integration Notes

- `test-agent` is backend-only in this repo snapshot.
- Generation route is synchronous today; job/event endpoints are scaffolded for
  status and SSE evolution.
- The LLM path uses Worktop model-client integration through the local adapter
  layer.
- Direct repository update is the intended beta behavior, with patch results,
  diffs, reasoning, confidence, and validation returned to the caller.
