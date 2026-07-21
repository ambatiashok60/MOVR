# ADR-0001: Server-enforced agent authority boundary

- Status: accepted
- Date: 2026-07-22
- Owners: RepoAgent maintainers
- Supersedes: none

## Context

RepoAgent supplies repository content and tool observations to an LLM, then may
execute model-proposed actions. Model output and repository instructions are
untrusted. Prompt instructions alone cannot reliably enforce authorization.

## Decision

The model may propose intent, plans, tool calls, and responses. Deterministic
backend code exclusively controls tool availability by mode, workspace path
resolution, command allowlisting, timeouts, output limits, snapshots, stale-write
guards, validation, persistence, and terminal run state.

Ask mode has no mutating or execution authority. Agent mode receives only the
explicitly registered tools; it does not receive arbitrary host authority.

## Alternatives considered

- Prompt-only restrictions: rejected because they are advisory and vulnerable to
  prompt injection.
- A privileged general shell tool: rejected because its authority cannot be
  bounded to the intended repository behavior.
- Client-side enforcement: rejected because clients are outside the server trust
  boundary and can be bypassed.

## Consequences

New tools require deterministic authorization and security tests. Some useful
actions remain unavailable until explicitly implemented. The executor and path
guard become high-criticality components. Production still requires process
isolation because application-level controls are defense in depth.

## Validation

`test_path_guard.py` and `test_tools_and_permissions.py` cover path escape, mode
denial, command allowlisting, and stale patch behavior. Agent lifecycle tests
verify mutation and validation through the authorized path.

## Rollout and rollback

This is a foundational invariant. A change that weakens it requires a superseding
ADR and security review; rollback means disabling the new authority/tool.
