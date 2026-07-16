# AI Workspace — Functional Guide

## Purpose

AI Workspace provides repository-aware Ask and Agent modes inside the Worktop shell. Ask explains
code without mutation. Agent explores the repository, proves a root cause, proposes changes,
validates and scores them, then stages diffs for explicit review and transactional Apply.

## Navigation and workspace setup

The combined preview places `AI Workspace` after `Test Gen` in the left navigation. Opening
`/ai-workspace` shows repository/branch selection, file explorer, conversation and a bottom composer.
The host owns authenticated repository access and branch selection.

## Ask mode

```text
Question
→ selected files + repository instructions + learned memory
→ recent conversation
→ data-governance filter
→ Worktop LLM
→ conversational answer
```

Ask cannot write or apply files and must never claim that it did.

## Agent mode

```text
Goal
→ bounded discovery turns
→ read/search/list observations
→ root-cause + evidence gate
→ plan and complete file proposals
→ deterministic validation
→ one bounded repair
→ isolated worktree/copy staging
→ engineering quality/risk review
→ diffs
→ Keep/Reject
→ transactional Apply
```

The agent cannot call Apply. Repeated identical tools and excessive turns are hard loop-safety
limits; token/cost estimates are review findings rather than blockers.

## Context and learning

AI Workspace reads user-owned repository guidance from `AGENTS.md`, `CLAUDE.md`,
`.github/copilot-instructions.md` and `.ai-workspace/instructions.md`. It also maintains external,
repository-keyed Markdown memory containing only validated root causes, evidence and affected files.
It does not modify model weights or silently write memory into the repository.

## Review and Apply

Proposed files remain staged. Review displays plan, root cause, evidence, validation, risk, quality
score and diffs. The user keeps or rejects files. Apply locks the repository, verifies proposal-time
hashes, snapshots targets, writes atomically, journals operations and rolls back partial failures.

## Preview behavior

The real FastAPI routes can run with `AI_WORKSPACE_ALLOW_MOCK_LLM=true`. The mock produces a safe
`AI_WORKSPACE_PREVIEW.md` proposal, allowing Ask, Agent, diff, review and Apply to be demonstrated
without Worktop model credentials.

## Current limitations

Background execution/live frontend SSE, cancellation/retry, multi-instance event fanout and full
repository-native compiler-driven repair remain production milestones. See `ALIGNMENT_PLAN.md`.

