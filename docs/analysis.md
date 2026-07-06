## Analysis made so far based on the repos

The core discovery is this:

**All repos support API integration testing, but they do not use the same test stack or maturity level. So Worktop should not force a standard framework. It should discover the repo’s current pattern and generate tests that fit it.**

---

## 1. Common patterns across repos

Across the repos, we identified these common foundations:

| Area              | Common discovery                                                 |
| ----------------- | ---------------------------------------------------------------- |
| Language          | Java / Spring Boot                                               |
| Test framework    | JUnit 5                                                          |
| Integration style | `@SpringBootTest`                                                |
| Build execution   | Maven Surefire / Failsafe style split                            |
| Coverage          | JaCoCo                                                           |
| CI objective      | Fast, deterministic, controlled dependency testing               |
| Stage objective   | Real deployed environment validation                             |
| Test naming       | `*Test.java` and `*IT.java` style                                |
| Config model      | `application-test.properties` and `application-stage.properties` |

The important pattern:

```text
CI = controlled dependencies + mocks/stubs + test profile
Stage = real services + real auth + stage profile
```

---

## 2. Repo diversification

| Repo                   | Main style            | HTTP mocking           | DB                   | Async / infra                  | API style      | Maturity     |
| ---------------------- | --------------------- | ---------------------- | -------------------- | ------------------------------ | -------------- | ------------ |
| **BenBundles**         | Service orchestration | WireMock               | MySQL test DB        | Kafka + gRPC                   | REST           | Medium       |
| **Flex Rates**         | Config/toggle heavy   | MockBean / layer mocks | H2/MySQL             | Kafka, Temporal off, Redis off | REST/gRPC      | Medium-high  |
| **Accruals**           | Event-driven          | MockWebServer          | MySQL Testcontainers | EmbeddedKafka                  | REST/events    | Lower-medium |
| **BenPlanLib Mapping** | Mature balanced       | WireMock               | MySQL container      | gRPC, logs, reporting          | REST/rules     | High         |
| **Holidays**           | Enterprise pipeline   | MockWebServer          | H2                   | gRPC, Temporal mocks           | REST + GraphQL | High         |

---

## 3. Key conclusion from comparison

The right Worktop principle is:

```text
Standardize the workflow, not the tech stack.
```

So Worktop should not say:

```text
Use WireMock.
Use Testcontainers.
Use H2.
Use GraphQL tester.
```

Instead, it should say:

```text
This repo already uses WireMock, so generate WireMock-style tests.

This repo already uses MockWebServer, so generate MockWebServer-style tests.

This repo disables Temporal/Redis in CI, so do not start them.

This repo uses application-stage.properties, so stage tests should use that profile.
```

---

## 4. CI vs Stage analysis

We clarified that **not all CI tests should run in Stage**.

CI tests are broader:

```text
happy path
validation failures
negative cases
downstream failures
timeouts
DB persistence
mocked contract behavior
Kafka/event behavior where needed
```

Stage tests are leaner:

```text
happy path
real auth
critical downstream compatibility
response contract
deployment/config validation
non-destructive smoke flow
```

So the model should not be:

```text
CI suite = Stage suite
```

The model should be:

```text
Scenario
   ↓
Execution classification
   ↓
CI implementation
Stage implementation
or both
```

---

## 5. Scenario-first model

This became the strongest design insight.

Worktop should not internally think in terms of “tests” first.

It should think in terms of:

```text
Business Scenario
   ↓
Execution Target
   ↓
Generated Implementation
```

Example:

| Scenario                   | CI | Stage | Reason                      |
| -------------------------- | -: | ----: | --------------------------- |
| Create bundle successfully |  ✅ |     ✅ | Core business flow          |
| Missing mandatory field    |  ✅ |     ❌ | Deterministic validation    |
| Downstream 500             |  ✅ |     ❌ | Mock-driven resilience      |
| Unauthorized request       |  ✅ |     ✅ | Real auth must be validated |
| Response contract          |  ✅ |     ✅ | Stage compatibility risk    |
| DB persistence             |  ✅ |     ✅ | Critical state validation   |

This avoids generating unnecessary stage tests.

---

## 6. Repository maturity analysis

We also identified three repo types:

### Greenfield / new repo

```text
few APIs
few or no integration tests
few fixtures/stubs
no strong convention yet
```

Worktop role:

```text
bootstrap integration testing foundation
generate initial conventions
create first CI + stage packs
```

### Growing repo

```text
some integration tests
some stubs/fixtures
mixed quality
some duplication
```

Worktop role:

```text
reuse existing patterns
detect gaps
generate missing scenarios
extend existing test structure
```

### Mature repo

```text
many integration tests
strong conventions
rich helper utilities
many fixtures
stage strategy may already exist
```

Worktop role:

```text
do not create duplicate suite
reuse and extend
fill only uncovered gaps
classify existing scenarios for CI/stage
```

---

## 7. Two-axis repo classification

We decided repo age alone is not enough.

Worktop should classify by:

```text
Testing maturity
+
System complexity
```

Testing maturity:

```text
Greenfield
Growing
Mature
```

System complexity:

```text
Simple: REST only
Medium: REST + DB + one downstream
Complex: REST + DB + Kafka/gRPC/GraphQL/Temporal/Redis
```

This creates better orchestration decisions than just “new vs old repo.”

---

## 8. Agent design analysis

We started with 8 agents, then refined it.

Recommended V1 agents:

| Agent                                         | Purpose                                        |
| --------------------------------------------- | ---------------------------------------------- |
| **1. Repository Discovery Agent**             | Understand repo test architecture              |
| **2. Story/API Scope Agent**                  | Map JIRA/story/diff to affected APIs           |
| **3. API Discovery Agent**                    | Discover endpoint contracts, DTOs, validations |
| **4. Dependency Discovery Agent**             | Build API dependency graph                     |
| **5. Existing Test Intelligence Agent**       | Find reusable tests, fixtures, helpers, stubs  |
| **6. Scenario Planning Agent**                | Create business scenarios                      |
| **7. Execution Classification Agent**         | Decide CI, Stage, or both                      |
| **8. Test Implementation + Validation Agent** | Generate files, run, repair, report            |

Key point:

```text
Do not create WireMock Agent, GraphQL Agent, Testcontainers Agent.
```

Those would make Worktop technology-driven.

Instead:

```text
Agents should be decision-driven.
Technology is discovered from repo profile.
```

---

## 9. Input analysis

Best V1 input is:

```yaml
jira_id: STORY-123
repo: selected-api-repo
branch: feature/story-123
target_environments:
  - ci
  - stage
```

Optional:

```yaml
api_scope:
  - POST /bundles
execution_preference:
  ci: full
  stage: smoke
auth_context:
  stage_auth_required: true
```

JIRA alone is not enough.

Worktop needs:

```text
JIRA story
repo
branch
source code
existing tests
config files
CI/stage profiles
```

---

## 10. Output analysis

Worktop should produce:

```text
Repository Integration Profile
API Inventory
Dependency Graph
Existing Test Intelligence Report
Scenario Manifest
Execution Classification Matrix
Generated CI integration tests
Generated stage smoke/contract tests
Generated fixtures/stubs/config updates
Validation report
Manual action list
```

Example output:

```yaml
scenario_manifest:
  api: POST /bundles
  scenarios:
    - id: SCN-001
      name: Create bundle successfully
      ci: true
      stage: true
    - id: SCN-002
      name: Missing required field
      ci: true
      stage: false
    - id: SCN-003
      name: Pricing service failure
      ci: true
      stage: false
    - id: SCN-004
      name: Response contract validation
      ci: true
      stage: true
```

---

## 11. V1 scope decided

We explicitly removed:

```text
unit tests
UI tests
Playwright
Suite Optimizer
repository health
performance tests
full GraphQL
full Kafka/gRPC generation
Pact/contract framework
multi-repo orchestration
```

V1 focuses only on:

```text
API integration tests for Java Spring Boot repos
CI + Stage execution
Scenario-first planning
Repo-aware generation
No forced tech stack
```

---

## Final conclusion

The analysis so far says Worktop V1 should be:

> **A repository-aware API integration testing platform that discovers existing Spring Boot testing conventions, plans business scenarios, classifies them for CI and Stage, and generates the required integration test implementations, fixtures, stubs, and validation reports without forcing teams to change their tech stack.**
