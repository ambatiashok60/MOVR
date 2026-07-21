# Architecture decision records

Use an ADR for a decision that is expensive to reverse, changes a trust or data
boundary, affects multiple components, introduces a production dependency, or
creates a durable compatibility constraint. Small local implementation choices
belong in code and tests.

## Lifecycle

1. Copy `0000-template.md` to the next four-digit number and a short slug.
2. Open it as `proposed` before implementation when meaningful alternatives exist.
3. Record evidence and consequences, not a meeting transcript.
4. Mark it `accepted` when the decision is approved.
5. Never rewrite history after adoption; add an ADR that `supersedes` the old one.

## Index

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-server-enforced-agent-boundary.md) | accepted | Server-enforced agent authority boundary |

The numbered decisions summarized in `ARCHITECTURE.md` predate this ADR log.
Future material changes should receive individual ADRs here.
