# Implementation Log — 2026-07-14

Three workstreams completed in one session. Nothing committed — all changes sit in working trees for manual commit.

| Workstream | Branch | Checkout | Verification |
|---|---|---|---|
| 1. test-agent structural fixes | `codex/test-agent-patch-validation` | `~/Documents/movr/MOVR` | 236/236 pytest, ruff clean |
| 2. test-agent agentic feedback loops | `codex/test-agent-patch-validation` | `~/Documents/movr/MOVR` | (same suite; included in 236) |
| 3. api-agent per-scenario Run/Abort | `codex/api-agent-scenario-codegen` (from origin/main) | worktree `~/Documents/movr/MOVR-api-agent` | 96/96 pytest, ruff clean; frontend via CI |

---

## Workstream 1 — test-agent structural fixes

**Problem (from production logs):** the decision agent correctly identified an existing test to extend (title + file + line 160, confidence 0.95), but the pipeline downgraded to `append_new_test` with `reason=no_valid_existing_test_context`. Root cause: an orchestration/context-contract gap — agent discoveries were never converted into deterministic structured context.

All paths under `test-agent/worktop/test_agent/app/`.

### Step 1.1 — Bridge agent discovery → structured ExistingTestContext
- `services/generation_orchestrator.py`
  - New `_parse_spec_tests(repo_path, file_path)` — parses one spec file from the live workspace (extracted from the anchor path's existing inline re-parse; reused in `_resolve_anchor_flow_context`).
  - New `_reparse_extension_target(action, repo_path, fallback_file)` — when the static candidate inventory misses, re-parses the agent-selected file and resolves **line-first** (start_line within a test's range), **normalized-title second**, nearest-line for duplicate titles; ambiguity returns None (never guesses).
  - `_resolve_existing_test_context` gained `repo_path` and the re-parse fallback; logs `recovered_via_reparse`.
- `services/test_action_service.py` — `_bind_selected_test_identity` no longer overwrites an agent-discovered `target_file_path` with a static candidate from a different file.

### Step 1.2 — Bounded retry with structured feedback before downgrade
- `config.py` — new `extension_resolution_agent_retries: int = 1`.
- `generation_orchestrator.py` — the `existing_test_context` stage became `_resolve_extension_target_with_retry`: static match → live re-parse → up to N decision-agent re-invocations with feedback listing the parser-validated tests (file, title, line range, describe) and why resolution failed; retried decisions are re-gated (reconcile → confidence) exactly like first pass. `_ensure_safe_extension_action` gained a `reason` param (`existing_test_resolution_failed_after_retry`) threaded into log + DecisionTrace evidence.
- Feedback threading: optional `feedback` param on `TestActionService.decide` → `TestActionDecisionAgent.decide` (appended to prompt).

### Step 1.3 — Structural anchor insertion (`insert_test_after_anchor`)
- `schemas/behavioral_test_unit.py` — `AnchorFlowContext` += `start_line`/`end_line`.
- `schemas/code_patch.py` + `patching/patch_planner.py` — new op `insert_test_after_anchor` (requires `target_test_title`).
- `patching/scoped_patch_writer.py` — new branch: resolve the anchor's fresh byte offsets via `find_test_block`, insert directly after it, verify the anchor sits inside the target describe. Shares the exactly-one-test and duplicate-title guards with the append family.
- `generation_orchestrator.py` — `_bind_append_to_anchor_describe` rewritten: validate **before** mutating (was mutate-then-silently-return), anchor-first binding, unique-describe fallback, else returns a failure reason that becomes a **blocking** `anchor_binding` plan-guard check feeding the existing repair loop. `_append_integration_check` covers the new op.
- `prompts/patch_review_prompt.py` — repair prompt preserves the new op instead of flipping back to `append_test`.

### Step 1.4 — Parser/validation contract consistency (+ real bug found)
- `tools/playwright_parser_tool.py` — `extract_tests(..., *, source="file")`; logs disambiguate `source=file` vs `source=generated_snippet` (resolves the misleading `tests=1` vs `discovered_tests=15`).
- `patching/scoped_patch_writer.py` — new `_assert_structural_outcome(patch, before, after)`: re-parses both versions pre-disk; append family must yield count+1 with the generated title in the target describe; `replace_test` must keep count with the target title present. Transactional (writer writes only after all patches pass).
- `validation/playwright_validator.py` — `_patch_outcome_messages`: generated/target title must exist in the patched file (and inside the target describe), feeding the post-write repair loop.
- **Bug found by the new assertion:** `find_describe_insertion_offset` returned the *statement end* (the `;` after `});`), so `append_test` inserted tests **outside the describe body** with a stranded semicolon — exactly the brace-displacement failure from the logs. Fixed via `_find_matching_brace(..., include_statement_tail=False)` returning the callback's true closing brace.

### Step 1.5 — Tests
- New `tests/test_target_resolution.py` (re-parse recovery, line/title resolution, ambiguity, identity preservation, retry/feedback/exhaustion).
- Extended `tests/test_patch_validation.py` (anchor insertion ordering, blocking plan guard, structural-outcome guards, validator title/describe checks). One existing test updated to the new binder contract.

---

## Workstream 2 — test-agent agentic feedback loops

**Problem:** several stages were single-pass "static LLM" calls — errors were logged and the job degraded or died instead of the failure becoming feedback for a bounded retry.

### Step 2.1 — Gap A: writer failures enter the repair loop
- `_write_validate_and_repair`: both `_write_patches` call sites wrap `ValueError` (the writer's transactional, recoverable contract — duplicate title, not-exactly-one-test, unresolvable targets, structural-outcome violations) into a failed `patch_write` `ValidationCheck` via `_patch_write_failure`, entering the existing RepairAgent loop. Works even with `run_validation=False`. `OSError`/real bugs still crash.

### Step 2.2 — Gap B: placement validation + feedback retry
- `config.py` — `placement_resolution_agent_retries: int = 1`.
- `_validate_placement`: create_new targets must not exist; non-create targets must exist and contain ≥1 test or describe.
- `_decide_placement_with_retry`: decide → bootstrap-normalize (moved inside; bootstrap repos skip validation) → validate → retry the placement agent with feedback naming the reason + actual spec files → on exhaustion keep the original decision and flag `review_reasons` (soft fail).
- Feedback threaded through `SpecPlacementService.decide` → `SpecPlacementAgent.decide`.

### Step 2.3 — Gap C: anchor binding self-heals
- `_bind_append_to_anchor_describe`: when anchor + named describe are both unresolvable but the live file has **exactly one** describe → deterministic rebind (`rebound_to_sole_describe`), idempotent across repair re-binds. Otherwise the blocking reason now lists the file's live describe and test titles.

### Step 2.4 — Accumulated attempt history (all loops)
- Extension retry and placement retry accumulate per-attempt records (what the agent returned + why it failed) and prepend a *"Previous attempts and why they failed (do NOT repeat these)"* section to every feedback prompt.
- Repair loops share one continuous `repair_history` across plan-guard and post-write phases (`_summarize_validation_failure`, entries truncated at 300 chars); `RepairAgent.repair` gained `history`, rendered by `build_repair_prompt` (explicit "None; this is the first repair attempt" otherwise).
- Result: each retry is still a fresh invocation, but attempt N knows what attempts 1…N−1 tried and why they failed — a genuine closed loop rather than a stateless re-roll.

### Step 2.5 — Tests
- New `tests/test_write_repair_loop.py`, `tests/test_placement_resolution.py`; history-assertion tests in all three loop families. Total suite: **236 passing**.

---

## Workstream 3 — api-agent per-scenario Run/Abort (scope-doc implementation)

**Setup:** branch `codex/api-agent-scenario-codegen` cut from `origin/main`, checked out as a git worktree at `~/Documents/movr/MOVR-api-agent` (keeps uncommitted test-agent work isolated).

**Validation-first:** the scope doc was validated against origin/main before implementation. Backend already had the machinery (async task manager, abort + `_check_abort` checkpoints, SSE, idempotent replay) under `abort` naming; frontend had a globally-gated Generate button, a single stream-killing SSE subscription, an `abort()` method with zero callers, and no per-row execution state. The Functional table (the scope's assumed reference pattern) has none of this either.

**Locked decisions:** keep `abort/ABORTING/ABORTED` naming (frontend maps to UI states); one job per row (no `scenario_ids[]` batching); pragmatic tenant-ownership check on abort (no auth infra exists); idempotency key format frozen (branch isolation lives in the byte-equal payload check).

### Phase A — Backend contract (`api-agent/worktop/api_agent/app/`)
1. `schemas/queued_task.py` — `QueuedTask` += `status`, `reused_existing_job`.
2. `task_managers/api_test_generation_task_manager.py` — all three `enqueue_*` methods return `(task_id, reused)`; module helpers pass through (`enqueue_api_testgen_task` keeps its plain-string host contract); all three routes unpack (`api_test_generation_routes.py`, `api_scenario_routes.py`).
3. Progress: module-level `STAGE_PROGRESS` map (scope-doc percentages adapted to real stage names, both flows); `_publish` sets monotonic `job.progress` and passes it to SSE. `GenerationEvent` += `progress`, `GenerationJob` += `progress`, SSE `publish()` += `progress`.
4. `VALIDATING` deliberately **not** added as a backend status (SSE terminal sets untouched; the stage fires post-generation anyway) — frontend derives it from `stage === 'validating'`.
5. Tenant check: `errors.py` `TenantMismatchError`; dedicated **403** handler in `main.py` (generic handler would mis-report 400); `abort(task_id, tenant_id=None)` verifies `request_payload.tenant_id`; `/abort/{task_id}` accepts optional `tenant_id` query param (frontend always sends it).
6. `generation_options` (`validate_compilation` / `allow_supporting_files` / `modify_existing_tests`, behavior-preserving defaults) on `GenerateApiTestCodeRequest` with `effective_run_validation`; wired into `generated_file_guard.py` (supporting files kept-with-warning inside detected test locations; existing-test overwrites hard-rejected when disabled; `_in_detected_test_location` factored out of `_is_test_path`).

### Phase B — Frontend per-row state machine (`api-agent/frontend/test-generation/`)
1. `models/api-test-generation.model.ts` — `RowExecutionStatus` (`IDLE|QUEUED|RUNNING|VALIDATING|ABORTING|ABORTED|COMPLETED|FAILED`), `RowExecution`, `IDLE_EXECUTION`, `ACTIVE_EXECUTION_STATUSES`; `QueuedTask`/`GenerationEvent`/`GenerationJob` gained the new backend fields. `ApiScenarioTableRow` untouched — execution state lives in a parallel map so scenario refresh can't wipe it.
2. `store/api-test-generation.store.ts` — per-row `executions` signal map + `patchExecution`/`executionFor`; removed `generatingCodeForId`/`activeJob`/`events`; `generatedResult` → `lastCodeResult` (last-run panels).
3. `store/api-test-generation.facade.ts` — rewritten: `Map<taskId, Subscription>` per code job (structural fix for the second-run stream-kill bug), dedicated scenario subscription, event→state mapping (VALIDATING derived), `refreshRow` with guaranteed cleanup on every path, new `abort(row)` (optimistic ABORTING, revert on error, terminal via SSE), reused-job replay handled by the SSE buffer (no special-casing).
4. `services/api-test-generation.service.ts` — `abort(taskId, tenantId?)` with `tenant_id` query param (first real caller of the endpoint).
5. Table component — full state machine: Run / Abort / "Aborting…" / Run Again / Retry / Files(n); execution badge vs scenario status; per-row progress bar + stage text; global disable removed → rows run in parallel. SCSS for badges/progress.
6. Container binds `[executions]` + `(abortRun)`; `isApproving()` derives from the pending-approval row's execution; selectors' `isBusy` derives from the executions map; mocks updated in lockstep (signatures + progress values mirroring `STAGE_PROGRESS`).

### Phase C — Tests (+ latent bug found)
- New `api-agent/tests/test_run_abort_contract.py` (12 tests): enqueue reuse reporting, different-branch isolation (pins the frozen-key contract), tenant mismatch → `TenantMismatchError` (job untouched), matching/absent tenant abort paths, monotonic progress (0→10→30→frozen-at-30 on abort→100), `QueuedTask` defaults, all four guard-option behaviors, `effective_run_validation` precedence.
- **Latent bug found on origin/main:** `_reusable_task_id` crashed with `AttributeError` on the *first* enqueue of any key whenever a payload was passed (`job` None but `job.request_payload` evaluated) — the entire enqueue path was broken at HEAD; existing tests never exercised it. Fixed with a `job is None` short-circuit, pinned by the new tests.

---

## Verification summary

```bash
# test-agent (main checkout)
cd ~/Documents/movr/MOVR/test-agent && python3 -m pytest tests/ -q     # 236 passed
python3 -m ruff check <changed files>                                  # clean

# api-agent (worktree)
cd ~/Documents/movr/MOVR-api-agent/api-agent && python3 -m pytest tests -q   # 96 passed
python3 -m ruff check <changed files>                                        # clean
```

Frontend: no local typecheck possible (node v14, portable module without tsconfig) — CI validates. Manual mock-mode checklist for the PR: two rows running in parallel with independent progress; Abort mid-run → ABORTING → ABORTED → Run re-enabled; Run Again replays instantly via the idempotent SSE buffer; approval flow re-runs only its row.

## Deferred (explicitly out of scope)

- test-agent: AnchorReusePlan coverage-% step matching, dependency-closure source reuse, tree-sitter/real AST, running tsc/playwright.
- api-agent standards parity with test-agent (ranked gaps): structural patching instead of whole-file overwrite; deterministic parser context resolution; decision traces + confidence gating; critic/targeted repair with attempt history; doc refresh (`IMPLEMENTATION_PLAN.md` still says "backend scaffold only").
