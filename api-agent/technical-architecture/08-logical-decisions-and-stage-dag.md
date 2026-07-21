# Logical decisions and stage dependency DAG

## Two related workflows

Scenario generation creates a coverage proposal; code generation consumes a reviewed scenario. They
share repository evidence but must not be collapsed: scenario regeneration should not modify code, and
code generation should not silently rewrite the approved scenario.

```text
                    R0 Authorized repository snapshot
                     |
          +----------+-------------------+
          v                              v
R1 Endpoint/OpenAPI discovery     R2 Build/dependency/test discovery
          \                              /
           +----------> R3 RepoProfile/SourceContext
                              |
Story -> A0 normalize/ambiguity -> A1 coverage model
                              |          |
                              +----------+-> A2 scenario planning/value/dedup
                                                 |
                                         A3 reviewed scenarios
                                                 |
Selected scenario + R3 --------------------------+
                                                 v
                                         B0 refresh affected evidence
                                                 |
                                         B1 strategy selection
                                         /       |       \
                                  B2 placement B3 command B4 MockStubPlan
                                         \       |       /
                                          B5 generation plan
                                                 |
                                          B6 candidate files
                                                 |
                                      B7 guards/static validation
                                                 |
                                      optional B8 test execution
                                                 |
                                   failure -> B9 bounded repair -> B7
                                                 |
                                      B10 review/result/traceability
```

R1 and R2 may run concurrently and are reusable across both flows. B0 refreshes only files and graph
neighborhoods relevant to the selected scenario. B5 cannot proceed without an explicit strategy and
MockStubPlan, even when the plan says no mocks are required.

## Stage artifacts and reuse

| Artifact | Producer | Consumers | Reuse/invalidation |
|---|---|---|---|
| endpoint catalog | R1 | A1, A2, B0, B1 | revision + scanner/OpenAPI version |
| repository profile | R3 | A2, B1–B5 | evidence hashes + profiler version |
| scenario set | A2 | UI review, B0 | story + profile + prompt/coverage policy |
| strategy decision | B1 | B2, B3, B5, validators | profile + scenario target + registry version |
| MockStubPlan | B4 | B5–B10, review UI | dependency graph + scenario + policy version |
| candidate file set | B6 | B7–B10 | generation-plan + model/prompt version |
| validation evidence | B7/B8 | B9/B10 | patch + command + validator/environment version |

## Decision rules

| Decision | Evidence-backed default | Review condition |
|---|---|---|
| Framework | strongest existing test/build convention | conflicting or absent conventions |
| Spring mechanism | reuse RestAssured/MockMvc/WebTestClient already used | multiple viable stacks or new dependency required |
| WebClient dependency | MockWebServer/WireMock/Mockito based on existing seam | runtime bean/reflection prevents certainty |
| Testcontainers | dependency and repository convention already present | infrastructure, Docker or CI impact is uncertain |
| Target CI/stage/both | scenario risk plus available environment contract | stage safety/config is host-dependent |
| File placement | nearest compatible existing test package | new module/source root or ownership ambiguity |
| Execution | trusted allowlisted command in sandbox | disabled/untrusted environment; report `notRun` |

## Redundancy controls

All discovery results should be stored in an evidence catalog with repository revision, file hashes,
scanner version, confidence and source spans. The scenario and code workflows reference evidence IDs
instead of embedding repeated raw scans in prompts. Before scanning, check whether the requested graph
neighborhood is already fresh. Before calling the model, check whether the exact decision inputs and
prompt/policy version already produced a usable artifact.

Operational reports should expose per-stage cache hit, files visited, LLM calls, tokens, duration and
artifact consumers. Likely redundancy smells are code generation rerunning global endpoint discovery,
both repo services scanning the same build files independently, MockStubPlan rediscovering fixtures,
repair repeating full repository context, and SSE/job layers duplicating terminal-state ownership.
