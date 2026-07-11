# Architecture and generation flows

## Story to scenarios

```text
JIRA story + repository selection
 -> story normalization and ambiguity analysis
 -> endpoint/OpenAPI/source discovery
 -> dependency and authentication discovery
 -> scenario coverage planning
 -> positive/negative/contract/security/edge classification
 -> persisted reviewable scenarios
```

## Scenario to code

```text
approved scenario + current repository
 -> framework and convention discovery
 -> strategy selection
 -> MockStubPlan and risk classification
 -> file/change plan
 -> model generation
 -> deterministic guards and structural validation
 -> optional trusted test execution
 -> bounded repair or needsReview
```

The model selects among evidence-backed options; deterministic services enforce path, policy,
workspace locking, validation and review. Runtime-created dependencies and external infrastructure
remain uncertain and must be surfaced rather than invented.
