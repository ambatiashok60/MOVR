Based on all the repository screenshots you've shared, here's a consolidated **current API integration testing ecosystem analysis**. This is exactly the type of document I would put into `docs/01-discovery/`.

---

# Current API Integration Testing Ecosystem Analysis

## Executive Summary

The five repositories do **not** follow a single testing architecture. Instead, they represent different stages of evolution and different technical requirements.

However, they all converge on the same engineering goal:

```text
Developer Code
        ↓
Integration Tests
        ↓
CI Validation
        ↓
Stage Validation
        ↓
Deployment Confidence
```

The differences lie in **how** each repository isolates dependencies, manages infrastructure, and validates integrations.

This is the primary opportunity for Worktop.

---

# Repository 1 — BSS BenBundles

## Overview

This repository represents a **service orchestration** pattern.

The service communicates with multiple downstream systems and therefore emphasizes dependency isolation during CI.

---

## Current Testing Stack

### Framework

* Spring Boot
* JUnit 5
* SpringBootTest

---

### Build

* Maven
* Surefire
* Failsafe

Clear separation between

```text
Unit

↓

Integration
```

---

### HTTP Mocking

Uses

```text
WireMock
```

Purpose

* Stub downstream REST services
* Control response payloads
* Simulate failures

---

### Database

Uses

```text
Dedicated MySQL integration database
```

rather than H2.

This provides higher fidelity.

---

### Messaging

Uses

```text
Kafka Testcontainers
```

allowing

* producer validation
* consumer validation
* event publishing

---

### gRPC

Uses

```text
In-process gRPC server
```

instead of external servers.

---

### Configuration

Heavy use of

```text
DynamicPropertySource
```

to inject

* WireMock URLs
* Kafka ports
* DB properties

at runtime.

---

### Strengths

✓ High-fidelity integration tests

✓ Strong service isolation

✓ Real infrastructure simulation

✓ Good CI reliability

---

### Weaknesses

* Manual stub creation
* Manual fixture maintenance
* Stage regression appears separated/manual
* No intelligent scenario classification

---

### Worktop Opportunity

Worktop should generate

* WireMock mappings
* JSON fixtures
* SpringBootTest integration tests
* DynamicPropertySource wiring

without changing repository conventions.

---

# Repository 2 — Flex Rates

## Overview

This repository emphasizes

> Configuration flexibility

rather than infrastructure simulation.

---

## Current Testing Stack

### HTTP

Primarily

```text
MockBean
```

instead of WireMock.

More dependency injection

Less HTTP simulation.

---

### Database

Supports

```text
H2

or

MySQL
```

depending on configuration.

---

### Async

Uses

```text
Kafka

Temporal

Redis
```

but disables expensive services during CI.

Examples

```text
temporal.enabled=false

redis.enabled=false

cache=simple
```

---

### Strengths

Very fast CI

Low infrastructure cost

Highly configurable

---

### Weaknesses

Configuration complexity

Many feature toggles

Higher risk of configuration drift

---

### Worktop Opportunity

Worktop must first discover

which features are disabled

before generating tests.

Generation should respect

existing toggles.

---

# Repository 3 — Accruals

## Overview

This repository is the most

**event-driven**

of the group.

---

## Current Testing Stack

HTTP

```text
MockWebServer
```

instead of WireMock.

---

Database

```text
MySQL Testcontainers
```

---

Messaging

```text
EmbeddedKafka
```

instead of external containers.

---

Cleanup

Uses

active

```text
TRUNCATE
```

strategy

instead of rollback.

---

### Strengths

Realistic event validation

Good infrastructure realism

---

### Weaknesses

Few integration tests

Lower maturity

Limited scenario coverage

More manual cleanup

---

### Worktop Opportunity

Generate

* event-aware scenarios
* Kafka validation
* MockWebServer stubs
* cleanup utilities

rather than generic tests.

---

# Repository 4 — BenPlanLib Mapping

## Overview

This is the most mature repository.

It demonstrates the most balanced testing ecosystem.

---

## Current Testing Stack

HTTP

```text
WireMock
```

---

Database

```text
MySQL container
```

---

gRPC

```text
In-process
```

---

Additional capabilities

* Log verification
* Allure reports
* JMeter
* Better organization

---

### Strengths

Best repository structure

Clear separation

Rich tooling

High maintainability

---

### Weaknesses

Mostly manual expansion

No automated scenario planning

---

### Worktop Opportunity

Focus on

reuse

rather than regeneration.

Extend existing suites.

Generate missing scenarios only.

---

# Repository 5 — Holidays

## Overview

Enterprise-oriented repository.

Most advanced deployment pipeline.

---

## Current Testing Stack

Pipeline

```text
Jenkins
```

---

HTTP

```text
MockWebServer
```

---

Database

```text
H2
```

---

GraphQL

Present

---

Temporal

Mocked

---

Quality

* Sonar
* JaCoCo

---

### Strengths

Enterprise pipeline

GraphQL support

Pipeline maturity

---

### Weaknesses

More moving parts

Higher complexity

Requires repository awareness

---

### Worktop Opportunity

Generate

GraphQL-aware

integration scenarios

while respecting Jenkins conventions.

---

# Cross-Repository Comparison

| Capability     | BenBundles | Flex Rates | Accruals | BenPlanLib | Holidays |
| -------------- | ---------- | ---------- | -------- | ---------- | -------- |
| SpringBootTest | ✓          | ✓          | ✓        | ✓          | ✓        |
| JUnit5         | ✓          | ✓          | ✓        | ✓          | ✓        |
| WireMock       | ✓          | —          | —        | ✓          | —        |
| MockWebServer  | —          | —          | ✓        | —          | ✓        |
| MySQL          | ✓          | Optional   | ✓        | ✓          | —        |
| H2             | —          | ✓          | —        | —          | ✓        |
| Testcontainers | Kafka      | Optional   | MySQL    | MySQL      | Limited  |
| Kafka          | ✓          | ✓          | Embedded | Limited    | Limited  |
| gRPC           | ✓          | ✓          | ✓        | ✓          | ✓        |
| GraphQL        | —          | —          | —        | —          | ✓        |
| Stage Profile  | ✓          | ✓          | Partial  | ✓          | Partial  |

---

# Ecosystem Observations

## Observation 1

Every repository uses

```text
SpringBootTest
```

This should become Worktop's primary generation target.

---

## Observation 2

Every repository already has

an integration testing strategy.

Therefore

Worktop should

discover

before generating.

---

## Observation 3

No two repositories

use the same mocking strategy.

Therefore

technology-specific generation

is the wrong abstraction.

---

## Observation 4

CI is already reasonably mature.

The biggest inconsistency

is

Stage validation.

---

## Observation 5

Repositories contain

many reusable assets

such as

* fixtures
* helper classes
* stub mappings
* builders

These should be reused

instead of regenerated.

---

# Ecosystem Maturity

| Repository | Maturity    | Comments                                             |
| ---------- | ----------- | ---------------------------------------------------- |
| BenBundles | Medium      | Strong isolation, moderate automation                |
| Flex Rates | Medium-High | Excellent configurability, complex toggles           |
| Accruals   | Medium-Low  | Good infrastructure, needs broader scenario coverage |
| BenPlanLib | High        | Most balanced and mature testing ecosystem           |
| Holidays   | High        | Enterprise-grade pipeline and GraphQL support        |

---

# Major Gaps Across All Repositories

## Gap 1

No repository automatically discovers

existing testing conventions.

---

## Gap 2

Scenario planning

is manual.

---

## Gap 3

CI and Stage

are treated as separate activities

instead of

shared business scenarios.

---

## Gap 4

Mocks

fixtures

stubs

configuration

are manually maintained.

---

## Gap 5

No repository classifies

which scenarios belong in

CI

Stage

or both.

---

# Strategic Opportunity for Worktop

Rather than becoming another AI code generator, Worktop should position itself as a **Repository-Aware API Integration Test Intelligence Platform**.

Its responsibilities would be:

1. **Discover** the repository's integration testing architecture.
2. **Understand** APIs, dependencies, and existing reusable assets.
3. **Plan** business scenarios independent of execution environment.
4. **Classify** scenarios for CI, Stage, or both based on business criticality and execution suitability.
5. **Generate** repository-native integration test implementations, fixtures, and supporting infrastructure.
6. **Validate** by compiling, executing, repairing, and reporting.

This strategy allows Worktop to integrate into repositories with different testing stacks without requiring teams to adopt new frameworks or rewrite their existing testing ecosystem.
