# Decision specifications and traced execution

## Canonical decision artifacts

Scenario decisions must retain story source, operation evidence, category, preconditions, request partition,
expected response/state, priority, target and confidence. Code decisions additionally retain `RepoProfile`,
strategy candidates, selected strategy, placement, command, `MockStubPlan`, generated-file manifest,
validation evidence and review report. Every artifact references repository revision and producer version.

## Strategy scoring specification

Score candidates from existing tests, active build dependencies, test source roots, helper conventions and
known runnable commands. Existing working tests are the strongest signal. A dependency without usage is only
availability evidence. A strategy is ineligible when required dependencies or source roots are absent unless
the plan explicitly proposes dependency changes and requests review. Ties are not resolved by model preference;
they produce a ranked choice with trade-offs.

## Mock/stub decision specification

For each external interaction record boundary, protocol, call site, controllability, existing seam, mechanism,
data/behavior required, lifecycle, files, infrastructure needs, secrets/auth impact, confidence and approval.
Prefer an existing seam; otherwise choose the least invasive mechanism supported by the repository. A generated
test cannot claim completeness when the plan promises a stub/helper/resource that is absent. Runtime service
discovery, reflection and stage credentials remain unresolved until host evidence is provided.

## Job state and invariants

```text
queued -> running(discovery -> planning -> generation -> validation -> repair?)
       -> completed | needs_review | failed | aborted
```

- Scenario generation never writes repository files.
- Code generation consumes a versioned selected scenario.
- Endpoint/schema drift invalidates the prior scenario-to-code assumption.
- Exactly one strategy owns file generation and validation semantics.
- SSE and job polling expose one task-manager state; events do not independently mutate truth.
- `ENABLE_TEST_EXECUTION=false` yields `notRun`, not successful execution.

## Fully traced example

Story: “GET `/api/orders?status=PAID` returns matching orders and rejects an invalid status.” Discovery matches a
Spring controller and OpenAPI operation, enum DTO, bearer security and an existing RestAssured integration-test
package using Testcontainers PostgreSQL. Scenario generation creates positive filtering, invalid enum/400,
authentication/401 and response-contract scenarios; it does not invent a Kafka scenario because no operation
evidence requires it. The user selects the positive scenario. Refresh confirms the endpoint and DTO hashes.
Strategy selection chooses RestAssured over MockMvc because adjacent integration tests and commands use it.
Placement selects the existing orders integration spec. `MockStubPlan` reuses the PostgreSQL container and data
factory, with no HTTP stub. Generation adds fixture data, request and schema/assertion logic. Guards confirm only
the spec changed. Static validation passes; targeted Gradle execution passes. The result links story → operation
→ scenario → test method → validation command. If Docker were unavailable, the outcome would be inconclusive
or needs-review, not a code repair.

## Failure ownership matrix

| Condition | Responsible stage | Permitted action |
|---|---|---|
| source/OpenAPI disagreement | discovery | preserve both, rank evidence, request review if contract-critical |
| no eligible strategy | strategy | propose reviewed dependency/convention addition; do not fabricate framework |
| missing promised mock | generation/plan conformance | bounded regeneration, then needs-review |
| generated compile failure | generation | validator-directed repair |
| container/service unavailable | environment | no speculative code rewrite |
| scenario drift | refresh | stop and regenerate/reapprove scenario |
| stage safety unknown | host integration | require configuration/approval |

## Redundancy proof

Before adding a scanner or agent, identify its unique artifact and consumer. If it returns facts already present
in `RepoProfile` or `SourceContext`, extend the existing producer rather than adding another repository pass.
Golden traces should assert scanner-call counts, artifact reuse, strategy rationale, mock-plan completeness,
terminal state and absence of writes during scenario generation.
