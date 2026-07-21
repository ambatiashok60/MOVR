# Seamless agent experience

The chat path uses newline-delimited JSON from `POST /api/chat/stream`. The UI
receives `started`, `classified`, `plan`, `activity`, `tool`, `usage`,
`context`, `text`, `heartbeat`, `completed`, and `error` events without waiting
for the final agent result.

## Workflow behavior

- Simple prompts use at most two agent rounds.
- Repository analysis uses targeted evidence and six rounds.
- Architecture comparison uses eight rounds and stops after both entry points,
  orchestration, data flow, consumers, and recommendations are covered.
- Error diagnosis traces the failing symbol, callers, contracts, consumers,
  configuration, and tests before proposing a coordinated fix.
- Cross-layer changes trace a backend response or API route into frontend API
  types, service mapping, components, dialogs/cards, accessibility, and tests.
  Empty, intentionally skipped, failed, loading, and successful results are
  treated as distinct UI states; structured skip reason and confidence are
  preserved when available.
- Architecture migration uses a design checkpoint. The first pass cannot edit;
  the user approves the visible plan before phased proposals begin.

Independent read-only file searches can run concurrently. Changes, commands,
and stateful tools remain sequential.

## Repository freshness

The repository index stores one entry per file with size, nanosecond mtime, and
content hash. Every use compares the live manifest, reparses changed/new files,
reuses unchanged entries, and removes deleted files. Applying a proposal changes
the live metadata, so its files are reparsed on the next index use. The UI also
offers a forced refresh. Edits always verify live file hashes; cached content is
never the authority for applying a change.

The agent may propose updates to existing workspace files or creation of new
files. Nothing is written automatically: the user reviews the multi-file diff,
selects files or hunks, and explicitly applies the proposal. Live hashes guard
against overwriting files that changed after the proposal was prepared.

## Context and recovery

The stream reports estimated conversation and repository-context tokens plus
actual Bedrock input/output usage after every model round. Long history is
compacted while preserving recent turns and the active plan. Manual compaction
archives the original JSONL before replacing it. Session execution state stores
the workflow, plan, activity, status, and usage so a refreshed UI can recover.

## Time and observability

The 900-second request deadline is an emergency ceiling. Bedrock reads and tool
commands retain their own smaller bounds. The stream and backend logs emit a
heartbeat every ten seconds. Console records are mirrored into daily files at
`backend/logs/backend-YYYY-MM-DD.txt` without prompts, file contents, credentials,
or tokens.

Benchmark cold and warm indexing with:

```bash
cd backend
python scripts/benchmark_index.py /absolute/path/to/workspace
```
