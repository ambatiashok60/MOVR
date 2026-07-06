Yes. I actually think this is the most important document in the entire project. Every logical capability should answer four questions:

1. **Why does it exist?**
2. **What problem does it solve?**
3. **What are its inputs and outputs?**
4. **Why can't the next capability do this instead?**

If you can't answer those questions, the capability probably shouldn't exist.

Below is how I would define them.

---

# Capability 1 — Project Discovery

## Why is it needed?

Every repository is different.

One team may use Java + Maven + Spring Boot.

Another may use .NET.

Another may use Node.

Another may use GraphQL.

Another may use gRPC.

If Worktop starts generating tests without understanding the repository, it will immediately generate the wrong implementation.

Therefore this capability establishes **"What is this project?"**

---

## Problem it solves

Today

Developers first spend hours understanding

* repository structure
* framework
* testing framework
* project conventions
* configuration

before writing a single test.

Worktop should automate that understanding.

---

## Questions answered

```text
What language?

What framework?

How is it built?

How is it tested?

How is it deployed?

How is configuration managed?

Where are tests located?

Where are fixtures stored?
```

---

## Inputs

```text
Repository

Branch
```

---

## Outputs

```text
Project Profile
```

---

## Why can't another capability do this?

Because every capability after this depends on it.

Without discovery

API Discovery

Dependency Discovery

Generation

are all assumptions.

---

# Capability 2 — Project Intelligence

## Why is it needed?

Two repositories can both be Java projects but require completely different strategies.

Example

Repo A

```text
No integration tests
```

Repo B

```text
400 integration tests
```

Generating tests for these repositories should not follow the same workflow.

---

## Problem

Most AI tools treat every repository equally.

Worktop should adapt.

---

## Questions answered

```text
Is this repository

Greenfield?

Growing?

Mature?

Should we

Bootstrap?

Reuse?

Extend?
```

---

## Inputs

Project Profile

---

## Outputs

Project Strategy

---

## Why separate from Discovery?

Discovery finds facts.

Intelligence makes decisions.

Example

Discovery

```text
400 integration tests
```

Project Intelligence

```text
Reuse existing tests.
```

Those are different responsibilities.

---

# Capability 3 — Testing Ecosystem Discovery

## Why is it needed?

Knowing the repository isn't enough.

We need to understand

how testing works today.

---

## Problem

Different teams use

different

execution models.

Example

One team

```text
WireMock
```

Another

```text
MockWebServer
```

Another

```text
No mocks
```

Worktop should adapt.

---

## Questions answered

```text
How are integration tests executed?

How are fixtures managed?

How are reports generated?

How are stage tests executed?

What execution profiles exist?
```

---

## Output

Testing Ecosystem Report

---

# Capability 4 — Change Intelligence

## Why?

The repository may contain

500 APIs.

The current story changes

2.

Generating tests for everything

is wasteful.

---

## Problem

Scope.

---

## Questions answered

```text
What changed?

What APIs changed?

What DTOs changed?

What contracts changed?

What configurations changed?
```

---

## Output

Change Scope

---

## Why separate?

Discovery answers

"What exists?"

Change Intelligence answers

"What matters today?"

---

# Capability 5 — Service Discovery

## Why?

Worktop generates tests around

services

not files.

---

## Problem

Developers think

API

Business Capability

Service

not

Java classes.

---

## Questions answered

```text
What capabilities exist?

REST

GraphQL

gRPC

Consumers

Producers
```

---

## Output

Service Inventory

---

# Capability 6 — Dependency Intelligence

This is probably the second most valuable capability.

## Why?

Integration tests exist

because of dependencies.

Without dependencies

there is no integration.

---

## Questions answered

```text
What databases?

What queues?

What downstream APIs?

What caches?

What authentication?

What feature flags?

What configuration?
```

---

## Output

Dependency Graph

---

## Why separate?

Service Discovery finds

what exists.

Dependency Discovery finds

what everything touches.

---

# Capability 7 — Existing Test Intelligence

Probably the biggest differentiator.

## Why?

Repositories already contain

thousands of hours

of testing effort.

Throwing that away

is wrong.

---

## Problem

AI tools generate duplicates.

---

## Questions answered

```text
What already exists?

What can be reused?

What should be extended?

What is missing?
```

---

## Output

Reuse Report

Gap Report

---

# Capability 8 — Scenario Intelligence

This is the heart of Worktop.

## Why?

Developers don't think

"I need another Java test."

They think

"I need to verify this business behaviour."

Scenario Intelligence converts implementation changes into business verification.

---

## Problem

Today's tools generate code.

They don't reason about

business scenarios.

---

## Questions answered

```text
What should be tested?

Happy path?

Negative?

Business rules?

Persistence?

Authorization?

Contracts?
```

---

## Output

Scenario Manifest

---

# Capability 9 — Execution Intelligence

## Why?

Not every scenario belongs in every environment.

This was one of our biggest discoveries.

---

## Problem

Running everything in Stage

is expensive.

Running too little

is risky.

---

## Questions answered

```text
Should this run in

CI?

Stage?

Both?

Future environments?
```

---

## Output

Execution Matrix

---

# Why separate from Scenario Planning?

Scenario

"What should be tested?"

Execution

"Where should it be tested?"

Different decisions.

---

# Capability 10 — Test Design Intelligence

Another capability I think is unique.

## Why?

There is a large gap between

Scenario

↓

Code.

Developers first design

the test.

Then they implement it.

Worktop should do the same.

---

## Questions answered

```text
What data?

What fixtures?

What stubs?

What assertions?

What dependencies?

What execution flow?
```

---

## Output

Test Design

---

# Capability 11 — Test Generation

## Why?

Only now

should Java

(or any language)

be generated.

Everything else

was preparation.

---

## Problem

Today's tools jump

directly

to code.

---

## Output

Generated Artifacts

---

# Capability 12 — Validation Intelligence

## Why?

Generated code

is only useful

if it works.

---

## Questions answered

```text
Does it compile?

Does it execute?

Does it fail?

Can it be repaired?
```

---

## Output

Validation Report

---

# Capability 13 — Reporting Intelligence

## Why?

Developers need confidence, not just generated files.

A report explains **what Worktop discovered, what it generated, what it reused, what failed, and what still requires manual attention**.

---

## Questions answered

```text
What changed?

What scenarios were created?

What was reused?

Which files were generated?

What passed?

What failed?

What requires manual review?
```

---

## Output

Final Engineering Report

---

# Why this decomposition is important

This architecture intentionally separates **facts**, **decisions**, and **implementation**.

```text
FACTS
------
Project Discovery
Testing Ecosystem
Service Discovery
Dependency Discovery
Existing Test Intelligence

↓

DECISIONS
---------
Project Intelligence
Change Intelligence
Scenario Intelligence
Execution Intelligence
Test Design Intelligence

↓

IMPLEMENTATION
--------------
Test Generation
Validation
Reporting
```

This separation is what makes Worktop fundamentally different from tools like GitHub Copilot.

* **Copilot** largely starts from implementation: "Generate this test."
* **Worktop** first discovers facts, then makes engineering decisions, and only then generates implementation.

That layered approach makes the system explainable, easier to validate with developers, and adaptable across different repositories and technology stacks without changing the core orchestration. It also gives you natural review checkpoints before any code is written, which is likely to improve developer trust and adoption.
