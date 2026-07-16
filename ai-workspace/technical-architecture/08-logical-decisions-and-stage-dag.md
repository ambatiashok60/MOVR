# Logical decisions and stage dependency DAG

## Workflow selection

Ask mode is chosen when the goal is explanation, diagnosis or planning without mutations. Agent mode
is chosen only when the user requests implementation or a normal implementation workflow clearly
requires repository changes. Mode changes authority: Ask can read; Agent can stage bounded changes but
still cannot bypass policy, review or transactional Apply.

## End-to-end execution DAG

```text
W0 Bootstrap/auth/workspace validation
 |
W1 Session + goal normalization
 |
W2 Repository revision/fingerprint
 |
+-> W3 Instructions + durable memory retrieval
+-> W4 File/symbol/route/test graph retrieval
+-> W5 Explicit selected-file context
        \          |          /
         +------ W6 Context ranking/budgeting
                       |
              +--------+---------+
              |                  |
          Ask W7A              Agent W7B initial plan
              |                  |
          W8A answer      W8B evidence-gap decision
                                 |
                        W9 tool selection/execution
                                 |
                         W10 observation + graph/context update
                                 |
                 +---------------+----------------+
                 |                                |
          evidence insufficient             evidence sufficient
                 |                                |
             re-plan W7B                      W11 patch plan
                                                  |
                                         W12 isolated writes/diff
                                                  |
                                         W13 static/test validation
                                                  |
                                      optional bounded repair -> W12
                                                  |
                                         W14 engineering review
                                                  |
                                         W15 user decisions
                                                  |
                                      W16 transactional Apply/rollback
```

W3–W5 can be retrieved concurrently. W9 executes one bounded tool decision at a time unless tools are
explicitly independent and read-only. W11 is unavailable until the evidence gate is satisfied. W16 is
unavailable until review and hash-conflict checks pass.

## Logical decision table

| Decision | Autonomous condition | Review/stop condition |
|---|---|---|
| Ask vs Agent | authority is clear from requested outcome | mutation intent is materially ambiguous |
| Retrieve context | ranked graph neighborhood fits budget | relevant symbol/owner cannot be resolved |
| Select tool | least-powerful tool can close evidence gap | tool requires new authority or unsafe external action |
| Continue loop | new evidence reduces a named uncertainty | repeated observations, iteration limit or no progress |
| Create patch | impact set and acceptance evidence are known | public API impact or ownership remains uncertain |
| Repair | validation identifies a bounded defect | repair changes intended behavior or repeats failure |
| Apply | decisions approved, hashes match, policy allows | sensitive path, conflict, rejection or failed validation |
| Token budget | show estimate/usage as review information | hard stop only when host explicitly selects strict policy |

## Stage dependency and artifact registry

Every stage should read/write typed artifacts rather than passing unstructured prompt history:

| Artifact | Required by | Identity and invalidation |
|---|---|---|
| workspace snapshot | all repository stages | repository + revision + policy |
| instruction set | context/planning/review | file hashes + precedence policy |
| code subgraph | context, impact plan, validation choice | revision + parser/index version |
| context bundle | model turn | goal + selected files + evidence IDs + budget policy |
| plan | tools, UI, review | goal + evidence + planner version |
| observation | re-plan, audit | tool/input/workspace revision |
| patch set | validation/review/apply | base hashes + normalized diff |
| validation evidence | repair/review/apply | patch + command + environment |
| review decision | Apply | user/role + patch revision |

The proposed `CodeGraphProvider` from document 07 should make W4 incremental. Changed files invalidate
their AST nodes and dependent graph neighborhoods; unrelated graph artifacts remain reusable.

## Redundancy and loop review

An execution trace must record stage ID/version, input artifact IDs, output IDs, cache status, model/tool
calls, tokens, duration and reason for running. Before each stage, query compatible artifacts. Before
repeating a tool, compare its normalized input and repository revision with prior observations. Stop or
re-plan when a call would duplicate an observation without addressing a new uncertainty.

Review these smells regularly: context builder and Agent both scanning the repository; services loading
the same session independently; repeated full-tree searches after a local change; model re-summarizing
unchanged files; validation executing unchanged commands on an unchanged patch; SSE and polling each
mutating execution state; memory duplicating current repository instructions; and repair restarting the
whole plan rather than consuming validator evidence.

Removing a stage requires a consumer analysis over the workflow DAG. Merge stages only when they share
the same invalidation boundary and security authority. Otherwise the apparent duplication may be an
intentional evidence or safety boundary.
