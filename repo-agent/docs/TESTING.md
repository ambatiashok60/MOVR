# Test strategy and TDD playbook

**Audience:** contributors and reviewers.  
**Policy:** behavior changes start with an executable failing test. Defect fixes
start with a regression test that reproduces the defect.

## 1. Why TDD is the default

RepoAgent executes model-proposed actions against a developer's workspace. The
important behavior is found at boundaries—permissions, paths, persisted state,
event ordering, timeouts, and recovery—not merely in individual functions. TDD
makes those boundaries explicit before implementation and leaves an executable
record of the intended behavior.

The working loop is:

1. **Red:** express one observable behavior and prove the new test fails for the
   intended reason.
2. **Green:** make the smallest production change that passes the new test.
3. **Refactor:** improve names and structure while the suite remains green.
4. **Integrate:** run the next-broader test layer and update contracts/docs.

Do not write a test that already passes and call that the red step. If failure is
unsafe or impractical to demonstrate, record the reason in the pull request.

## 2. Test pyramid and ownership

| Layer | Location | Purpose | Expected characteristics |
|---|---|---|---|
| Unit | `backend/tests/test_*.py` | Pure rules and narrow boundaries | deterministic, isolated, sub-second |
| Service/component | `backend/tests/test_runs.py` | Agent lifecycle across real internal components | FakeLLM, temporary SQLite and workspace |
| Contract | backend tests + `docs/integration-contract.md` | REST models, enum values, SSE sequence/replay | provider-independent, exact payload assertions |
| Browser E2E | `frontend/e2e/repo-agent.spec.ts` | Critical user journeys across HTTP/SSE | few, high-value scenarios |
| Deployment smoke | environment pipeline | Health, streaming, persistence, identity | runs after deployment, never against user data |

Prefer the lowest layer that can prove the behavior. Add an E2E test only when
the browser, network, or frontend state machine is essential to the risk.

## 3. Change-to-test decision table

| Change | Minimum evidence |
|---|---|
| Path or file operation | traversal, absolute-path, symlink, valid nested-path tests |
| Permission/tool change | allowed and denied mode tests; failure does not mutate |
| Agent state transition | happy path, rejection/failure, terminal-state guarantee |
| SSE event change | monotonic sequence, replay, duplicate handling, terminal event |
| Persistence change | repository test using a fresh DB; restart/replay behavior if relevant |
| LLM provider change | fake/stub contract tests; error classification; timeout behavior |
| Frontend state change | reducer/component test; E2E for a critical lifecycle |
| Defect fix | regression test named for the externally visible failure |

## 4. Backend test pattern

Tests run without AWS. `tests/conftest.py` gives every test a temporary workspace
and SQLite database, then clears cached service singletons. Async scenarios use
`run_async`; completed agent runs use `drive_to_terminal`.

```python
def test_ask_mode_rejects_a_new_mutating_tool(workspace):
    async def go():
        with pytest.raises(ToolPermissionError):
            await ToolExecutor().execute(
                workspace=workspace,
                mode=AgentMode.ASK,
                tool_call=ToolCall(
                    tool_call_id="t1",
                    tool_name="new_mutating_tool",
                    arguments={},
                ),
            )

    run_async(go())
```

Test observable outcomes rather than private call order. Direct private access is
acceptable only for a fault-injection seam, as used by the watchdog test; prefer
a public seam when introducing new code.

## 5. Determinism and isolation

- Use `FakeLLM`; unit and component tests must not call Bedrock or the network.
- Use `tmp_path`; never read or modify the contributor's actual repository.
- Control time, identifiers, and failures at seams rather than sleeping.
- Assert terminal outcomes, persisted artifacts, and emitted events—not log text.
- A test must pass alone, in any order, and when the complete suite is repeated.
- Avoid snapshots for dynamic event payloads; assert the stable contract fields.

## 6. Commands and quality gates

Fast feedback while developing:

```bash
cd repo-agent/backend
python3 -m pytest -q tests/test_tools_and_permissions.py
python3 -m pytest -q tests/test_tools_and_permissions.py::test_executor_blocks_write_tool_in_ask
```

Required before review:

```bash
cd repo-agent/backend
python3 -m pytest -q

cd ../frontend
npm run build
npm run e2e
```

`npm run e2e` starts the backend and static preview according to
`playwright.config.ts`. Install Chromium once with
`npx playwright install chromium`.

Current tooling has no committed coverage, lint, type-check, or frontend unit
test configuration. Do not claim these as gates until configuration and a
ratcheted baseline are committed. The next quality investment should add gates
incrementally rather than introduce a large, arbitrary threshold.

## 7. Review checklist for tests

- The test name states behavior and condition, not implementation.
- The assertion would fail if the intended guarantee regressed.
- Failure output points to one behavior.
- Security and failure paths receive at least as much attention as happy paths.
- The test contains no real credentials, home-directory paths, or network calls.
- Contract changes update both producers, consumers, and
  `integration-contract.md` in one change.
- The suite is fast enough that contributors will run it locally.

## 8. Flaky-test policy

A flaky test is a production defect in the delivery system. Do not silently
retry it or weaken assertions. Capture the seed/timing/environment, open an
owner-visible issue, and fix or quarantine it with an explicit expiry date. A
quarantined test cannot count as release evidence.
