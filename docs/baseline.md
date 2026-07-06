I agree with that approach.

I would deliberately choose repositories that represent **three different architectural archetypes**, not necessarily the three easiest ones. That way, if Worktop succeeds on those three, it's much more likely to generalize to the others.

## Recommended Pilot Repositories

### 1. WFM (Mandatory)

**Why it's a must**

WFM is likely to have:

* Mature codebase
* Multiple APIs
* Existing integration tests
* Real business workflows
* High developer usage
* Good benchmark for brownfield repositories

This should become your **primary validation repository**.

Worktop should prove that it can **extend existing integration tests instead of creating new ones**.

Primary objective:

```text
Brownfield intelligence
Reuse existing tests
Gap detection
Scenario classification
```

---

### 2. Bundles

**Why**

Bundles represents service orchestration.

Expected characteristics:

* Multiple downstream services
* WebClient/REST integrations
* Database
* Kafka/gRPC
* Multiple business rules

This validates:

```text
Dependency Discovery

Scenario Planning

Mock/Stub Discovery

Stage Classification
```

This is probably your best repository for validating complex dependency analysis.

---

### 3. Third Repository

I'd choose based on what capability you most want to validate.

### Option A – BenPlanLib (My recommendation)

Reason:

* Mature integration testing
* Good conventions
* Existing helpers
* Existing fixtures
* Existing reports

This validates whether Worktop can integrate into a highly mature repository without creating unnecessary duplication.

---

### Option B – Flex Rates

Reason:

* Configuration-heavy
* Feature toggles
* More configuration intelligence

Choose this if you want to stress-test discovery.

---

### Option C – Holidays

Reason:

* GraphQL
* Jenkins
* Different execution model

I would **not** recommend this for V1 unless GraphQL is part of the release scope.

---

# My Recommendation

| Repository     | Purpose                                           |
| -------------- | ------------------------------------------------- |
| **WFM**        | Brownfield / mature repository (must-have)        |
| **Bundles**    | Service orchestration and dependency intelligence |
| **BenPlanLib** | Mature integration testing and reuse validation   |

This gives three very different ecosystems.

---

# Story Distribution

Each repository

```text
6 existing API development stories
```

Split as

```text
2 Small
2 Medium
2 Complex
```

Total

```text
3 repositories

×

6 stories

=

18 benchmark stories
```

---

# Why these repositories complement each other

### WFM

Validates

```text
Existing repository

↓

Existing tests

↓

Reuse

↓

Extension
```

---

### Bundles

Validates

```text
Complex dependencies

↓

Scenario generation

↓

CI

↓

Stage
```

---

### BenPlanLib

Validates

```text
Repository conventions

↓

Fixtures

↓

Helpers

↓

Avoid duplication
```

---

# Success Matrix

Each of the 18 stories should be evaluated across the same dimensions.

| Capability                 | Expected Result                         |
| -------------------------- | --------------------------------------- |
| Repository Discovery       | Correct project profile                 |
| Story Scope                | Correct APIs identified                 |
| Service Discovery          | Correct endpoints/contracts             |
| Dependency Discovery       | Correct downstream graph                |
| Existing Test Intelligence | Existing assets reused                  |
| Scenario Planning          | Correct business scenarios              |
| Execution Classification   | Correct CI/Stage assignment             |
| Test Design                | Appropriate fixtures, stubs, assertions |
| CI Generation              | Repository-native integration tests     |
| Stage Generation           | Lean stage smoke/contract pack          |
| Validation                 | Compile, execute, repair if needed      |

---

# One additional recommendation

Since you're using **existing completed JIRA stories**, capture the **developer implementation as the ground truth** for each story. For every benchmark story, record:

```text
JIRA Story
        ↓
Developer Code Changes
        ↓
Developer Integration Tests
        ↓
Developer Review Outcome
```

Then compare Worktop against that baseline:

```text
Developer Baseline
        vs
Worktop Discovery
        vs
Worktop Scenarios
        vs
Worktop Generated Tests
```

This gives you an objective benchmark throughout development and future releases. Instead of saying "the AI generated tests," you can measure how closely Worktop's understanding and outputs align with what experienced developers actually built. That is a much stronger validation strategy for the pilot.
