# Decision specifications and traced execution

## Turn and plan contracts

An Agent turn records goal version, plan version, repository revision, context artifact IDs, unresolved
questions, selected action, tool input, observation, information gained, confidence changes, usage and next
decision. A plan step records dependencies, required evidence, allowed authority, expected artifact and proof of
completion. “Done” is therefore evidence-based, not a model phrase.

## Next-action decision algorithm

1. Remove plan steps whose completion artifacts are already fresh.
2. Find incomplete steps whose dependencies are satisfied.
3. Rank their unresolved questions by downstream impact and uncertainty.
4. For the top question, enumerate available tools and cached observations.
5. Eliminate tools outside authority, path policy, command allowlist or remaining execution limits.
6. Rank remaining tools by expected information gain, precision, cost and risk.
7. Reuse an observation when tool, normalized input and snapshot match.
8. Execute one action, classify the observation and update graph/context.
9. Re-plan when evidence contradicts the plan; stop when no safe action can improve confidence.

This algorithm prevents the LLM from choosing tools solely by narrative preference. The model can propose a
choice, but `tool_selection_service.py` and `tool_execution_service.py` enforce eligibility and recording.

## Context precedence and compression

Policy and authenticated workspace facts rank first, then current repository instructions/source, explicit user
constraints, selected files, graph neighbors, fresh observations, durable memory and model inference. Compression
must retain goal, constraints, artifact IDs, decisions, failures, unresolved questions and source spans. It may
discard repetitive prose and already-consumed raw output. Memory never grants authority and is invalidated by
contradictory current evidence.

## Mutation and review invariants

- Ask mode cannot reach write, patch or Apply tools.
- Agent writes only to an isolated workspace until Apply.
- A patch contains base hashes and an explicit impact set.
- Public-contract or sensitive-path uncertainty forces review.
- Rejecting a foundational change invalidates dependent changes.
- Apply reacquires authorization/lock and verifies hashes.
- Exactly one transaction owns journal, atomic writes and rollback.
- One execution-state store owns terminal truth for polling and SSE.

## Fully traced example

Goal: “The API-to-browser wiring is broken; fix it.” W0 authorizes the repository and Agent mode because a fix is
requested. W1 defines success as the browser calling the configured backend route and rendering success/error
states. W2 loads route configuration, Angular service, environment/provider setup, backend router and DTOs; the
code graph links component → facade → service → URL token and backend route → DTO. W4 hypothesizes a prefix or
contract mismatch and creates inspect, compare, patch and validate steps. W5 reads the frontend service and
backend route, discovers `/api/api-test-generation` versus an old client prefix, and avoids re-searching files
already in the graph. Impact analysis finds the service token and integration example but no component changes.
W6 stages a configuration/provider correction rather than hard-coding a URL in the component. W7 type-checks and
runs the narrow relevant test; if no runnable Node environment exists, it records `notRun` plus static evidence.
W8 shows the one-file diff, route evidence and validation. Apply verifies the original hash, writes atomically,
invalidates the service/config graph nodes and emits one completed state.

## Failure and escalation matrix

| Condition | Decision |
|---|---|
| repeated search returns no new symbols | stop repeating; widen graph query once or request review |
| model proposes forbidden tool/path | reject action, retain reason, select eligible alternative |
| tool output contradicts memory | invalidate memory and re-plan from current evidence |
| test command is unavailable | static proof + explicit notRun; do not claim completion evidence |
| patch changes public DTO unexpectedly | expand impact analysis and require review |
| base hash changes before Apply | conflict state; regenerate diff against new snapshot |
| repair repeats same signature | terminate repair and expose failure evidence |

## Implementation review checklist

For each new stage require a typed artifact, unique responsibility, eligibility rule, authority boundary, cache
key, invalidation rule, telemetry, failure owner and golden trace. A stage without a unique output is probably
redundant. A stage sharing output but not authority may be an intentional safety boundary and should remain
separate. Validate the architecture using traces that assert exact tools/stages executed, artifacts reused,
decisions reviewed, state transitions and repository writes.
