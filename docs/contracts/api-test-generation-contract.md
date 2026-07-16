# API Test Generation — Frontend ⇄ Backend Contract

Audience: backend engineers integrating the WorkTop **Test Gen › API Tests** UI
with `api-agent`. The Angular feature lives in
`api-agent/frontend/test-generation`; the mock layer in
`api-agent/frontend/test-generation/mocks` is an executable copy of this
contract — every fixture mirrors a real `worktop.api_agent` schema.

Base prefix (dev proxy): `/api/api-test-generation` → api-agent FastAPI
(`uvicorn worktop.api_agent.app.main:app --port 8091`; OpenAPI at `/docs`).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/generate-api-scenarios` | Queue scenario generation for a story. Returns `{queued, task_id}`. |
| POST | `/generate-api-test-code` | Queue code generation for one scenario. Returns `{queued, task_id}`. |
| GET | `/jobs/{task_id}` | Full job (status, stage, events, result). Polled after terminal SSE event. |
| POST | `/abort/{task_id}` | Request abort; job transitions `aborting → aborted`. |
| GET | `/events/{task_id}` | **SSE.** Named events: `queued, running, progress, aborting, aborted, completed, failed`; each `data:` is a `GenerationEvent` JSON. |
| POST | `/checkRepoProfile` | `{repo_path}` → whether a repo profile exists. |
| POST | `/generateRepoProfile` | `{repo_path, overwrite?}` → build repo profile. |

## Request payloads

`GenerateApiScenariosRequest`: `user_story_hierarchy_id`, `user_story_id?`,
`tenant_id?`, `repo_path`, `story_title?`, `story_description?`,
`acceptance_criteria[]`, `additional_context?`, `branch?`.

`GenerateApiTestCodeRequest`: `user_story_hierarchy_id`, `api_scenario_id`,
`scenario_name`, `scenario_steps[]`, `tenant_id?`, `repo_path`, `story_id?`,
`method?`, `endpoint?`, `service_name?`, `execution_target` (`ci|stage|both`),
`assertions[]`, `branch?`, `run_validation`, `additional_context?`,
`approve_high_risk_mocks?` (set true when the user approves a high-risk mock
plan in the Mock Plan Review dialog).

## Scenario result (`ApiScenarioGenerationResult`)

`task_id`, `user_story_hierarchy_id`, `user_story_id?`, `scenarios[]`,
`repo_findings[]`, `warnings[]`, plus enterprise fields:
`needs_review`, `review_reasons[]`, `scenario_value` (verdict per scenario:
`NEW_COVERAGE | MEANINGFUL_VARIATION | PARTIAL_DUPLICATE | FULL_DUPLICATE |
LOW_VALUE` — powers Consolidate), `traceability` (acceptance criterion →
scenario matrix).

Each `ApiScenario`: `api_scenario_id`, `scenario_name`, `scenario_type`
(`positive|negative|contract|auth|edge`), `service_name?`, `method?`,
`endpoint?`, `priority` (display string, e.g. `P0`), `execution_target`,
`reason`, `scenario_steps[]`, `assertions[]`.

> **Backend TODO (new in this design):** `dependencies?: {label, kind}[]`
> where `kind ∈ database|authentication|service|other` — drives the
> Dependencies badges (DB / Auth) in the scenarios table. The UI renders `[]`
> until the backend supplies it.

## Code result (`ApiTestGenerationResult`)

`task_id`, ids, `generated_files[]` (`path, operation, test_target, summary`),
`validation?` (`passed, command, summary, details[]`), `summary`,
`strategy_name/confidence/reasons`, `reused_examples[]`,
`source_files_used[]`, `mock_stub_plan?` (incl. `risk_level`,
`approval_required`, `approval_reasons[]` — triggers the Mock Plan Review
dialog), `warnings[]`, `needs_review`, `review_reasons[]`, `budget?`
(usage + exceeded thresholds), plus enterprise fields `coverage`,
`traceability`, `review_report` (markdown for the drawer's Gen Plan tab) and
`manifest` (reproducibility fingerprint).

## SSE `GenerationEvent`

`{task_id, event_type, stage, message, payload, created_at}` — stages match
the orchestrator's stage names (`scanning_repository`,
`planning_mocks_and_stubs`, `selecting_generation_strategy`,
`generating_test_code`, `validating`, …). Native EventSource cannot send an
Authorization header: keep cookie auth for this route or swap the events
service for the host's fetch-based SSE client.

## Running the demo

- **Pure browser (design review):** `DEMO.useTestGenMocks = true`
  (`ai-workspace/frontend/src/app/demo.config.ts`), then
  `cd ai-workspace/frontend && npm start` → http://127.0.0.1:4200/test-generation
- **Against the real service:** flip the flag to `false`, run
  `cd api-agent && uvicorn worktop.api_agent.app.main:app --port 8091`
  (no WorkTop install needed — the LLM factory falls back to
  `LocalFallbackLLMClient`), and use the same URL; the dev proxy forwards
  `/api/api-test-generation` to :8091.
