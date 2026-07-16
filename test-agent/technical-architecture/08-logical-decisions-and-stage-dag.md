# Logical decisions and stage dependency DAG

## Why this workflow exists

Functional-test generation is split into evidence, decision, mutation and proof stages. Repository
facts are collected once and normalized before model reasoning. Mutation cannot start until placement,
ownership and intended coverage are known. A generated patch is never considered complete until it
passes deterministic guards and produces a review artifact.

## End-to-end stage DAG

```text
S0 Request normalization + policy
 |
 v
S1 Repository fingerprint ───────────────┐
 |                                      |
 +-> S2 Technology/source parsing       |
 |      +-> S3 Dependency/import graph  |
 |      +-> S4 Existing test inventory  |
 |                                      |
 +--------------------------------------+-> S5 Functional intent
                                              |
                       S3 + S4 + S5 ----------+
                                              v
                                      S6 Candidate ranking
                                       /       |       \
                              S7 Placement  S8 Ownership  S9 Locator/reuse
                                       \       |       /
                                        v      v      v
                                      S10 Test action + flow merge
                                              |
                                      S11 Code generation
                                              |
                                      S12 Patch plan and guards
                                              |
                                      S13 Static/quality validation
                                              |
                               optional S14 Repository execution
                                              |
                               failure -> S15 Bounded repair -> S13
                                              |
                                      S16 Result/review/traceability
```

S2–S4 can run from the same snapshot and can be reused. S7–S9 are independent only after S6 has fixed
the candidate set. S11 is blocked until S7–S10 are resolved. S14 is optional; skipping it must produce
`notRun`, never a false pass.

## Stage contract and reuse rules

| Stage | Requires | Produces | Reuse key | Re-run when |
|---|---|---|---|---|
| S1 fingerprint | authorized repo snapshot | file hashes/config profile | commit + policy version | files or policy change |
| S2 parsing | S1 | symbols/routes/bindings | file hash + parser version | source/parser changes |
| S3 graph | S2 | typed dependency edges | parsed-node hashes | node/edge resolution changes |
| S4 inventory | S2, S3 | tests/helpers/fixtures/coverage | graph revision | relevant graph changes |
| S5 intent | request, story, selected context | normalized behaviors | request/story hash + prompt version | intent or prompt changes |
| S6–S10 decisions | S3–S5 | placement/action/locator plan | evidence IDs + decision version | evidence or constraints change |
| S11 generation | approved decision artifacts | candidate files | decision hash + model/prompt version | plan/model changes |
| S13 validation | candidate files | validation evidence | patch hash + validator version | patch/rules change |
| S14 execution | guarded patch + command | test evidence | patch + command + environment | any input/environment change |

## Core logical decisions

| Decision | Prefer autonomous when | Require review/fallback when |
|---|---|---|
| Reuse spec/helper | strong ownership and behavior match | multiple owners or possible semantic collision |
| Create a spec | no compatible test unit exists | placement confidence is low |
| Locator | stable existing test ID/role convention | only brittle DOM/CSS evidence exists |
| Merge flow | same setup, actor and state transition | merge would hide independent failure intent |
| Repair | validator identifies a bounded local defect | repeated failure or behavior must change |
| Budget | estimate is within review policy | estimate is high; warn and continue unless strict mode |

## Redundancy and availability review

Before starting a stage, the orchestrator should query an artifact registry by reuse key. An artifact
records `artifactId`, type, repository revision, producer stage/version, inputs, confidence, timestamp
and source spans. A stage is skipped only when the artifact is compatible and fresh; the skip and reused
artifact IDs belong in the decision trace.

Redundancy signals include the same files parsed twice, two agents answering the same ownership question,
generation rediscovering helpers already present in inventory, validation rerunning on an unchanged patch,
or repair rebuilding the entire context. Track stage duration, input/output hashes, cache hit, LLM calls,
tokens and downstream consumers. Delete or merge a stage only after confirming no consumer depends on its
unique artifact or evidence gate.
