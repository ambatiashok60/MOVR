# Migration-Grade Agent Architecture

## Product Standard

The product is a local coding agent for repository exploration, migrations,
multi-file editing, validation, and reviewed application. Its quality bar is an
iterative coding-agent workflow, not a single prompt containing a few files.

A user can:

1. Open any allowed local folder, whether or not it is a Git repository.
2. Select one file, many files, directories, or the entire workspace as scope.
3. Ask for a migration or change in natural language.
4. Let the agent explore dependencies and related files beyond the initial
   selection when permission allows.
5. Review the plan, live tool activity, proposed multi-file changes, validation
   results, and final diff.
6. Accept or reject files and hunks, request revisions, apply approved changes,
   or roll them back.

## Project Structure

```text
agentic-workspace-chat/
├── .env.example
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py                 API composition
│   │   ├── config.py               Backend-only environment settings
│   │   ├── bedrock.py              Current Bedrock adapter
│   │   ├── workspace.py            Current safe filesystem and diff layer
│   │   ├── models.py               Current API contracts
│   │   ├── agent/                  Planned agent runtime
│   │   │   ├── loop.py             Observe/plan/tool/result loop
│   │   │   ├── state.py            Durable run state and checkpoints
│   │   │   ├── prompts.py          Versioned system/task prompts
│   │   │   ├── context.py          Token budgets and context assembly
│   │   │   └── policies.py         Approval and execution policy
│   │   ├── indexing/               Planned large-workspace intelligence
│   │   │   ├── scanner.py          Ignore rules and incremental scan
│   │   │   ├── symbols.py          Language-aware symbol extraction
│   │   │   ├── chunks.py           Large-file structural chunking
│   │   │   ├── graph.py            Imports/references/dependency graph
│   │   │   └── search.py           Lexical, symbol, and semantic retrieval
│   │   ├── tools/                  Planned typed tool implementations
│   │   │   ├── filesystem.py       List/read/range-read/search/stat
│   │   │   ├── editing.py          Create/patch/rename/delete
│   │   │   ├── git.py              Optional status/diff/history
│   │   │   ├── validation.py       Tests, lint, build, type-check
│   │   │   └── registry.py         Schemas, policy, and dispatch
│   │   ├── review/                 Planned review/apply subsystem
│   │   │   ├── proposals.py        Isolated proposed workspace
│   │   │   ├── diffs.py            File/hunk diff model
│   │   │   ├── apply.py            Atomic selective application
│   │   │   └── rollback.py         Git and non-Git recovery
│   │   └── storage/                Planned filesystem state repositories
│   └── tests/
├── frontend/
│   ├── src/app/
│   │   ├── app.component.*         Current application shell
│   │   ├── api.service.ts          Current backend client
│   │   ├── workspace/              Planned tree, search, scope selection
│   │   ├── chat/                   Planned conversation and run timeline
│   │   ├── review/                 Planned diff and hunk review
│   │   └── settings/               Planned model and agent controls
│   └── package.json
└── docs/
    ├── ARCHITECTURE.md
    └── IMPLEMENTATION_PLAN.md
```

The planned directories describe intended boundaries; they should be created
incrementally with implementation, not as empty architecture ceremony.

## Agent Feedback Loop

```text
User request and selected scope
        ↓
Clarify only if essential; otherwise state assumptions
        ↓
Create an inspectable migration plan
        ↓
Explore workspace with bounded tools
        ↓
Retrieve relevant ranges, symbols, references, configs, and tests
        ↓
Update plan and propose edits in an isolated workspace
        ↓
Inspect resulting diff and re-read changed regions
        ↓
Run configured validation
        ↓
Diagnose failures and iterate within step/time/cost limits
        ↓
Present summary, evidence, validation, risks, and selectable diffs
        ↓
User accepts/rejects/revises files or hunks
        ↓
Revalidate stale-file hashes and atomically apply approved changes
        ↓
Optional final validation and rollback checkpoint
```

Every tool call and result becomes an observable run event. The UI must show
what the agent is reading, why it expanded scope, what it changed, and what
validation passed or failed. Internal model reasoning is not exposed; concise
action summaries and evidence are.

## Large Files and Large Workspaces

Large input must never be blindly truncated or sent wholesale to the model.
The backend owns a hierarchical context system:

- Scan metadata first: paths, languages, sizes, manifests, and ignore rules.
- Build symbol outlines and import/reference edges where parsers are available.
- Split files along structural boundaries such as classes, functions, templates,
  configuration objects, and sections; use line windows only as a fallback.
- Retrieve exact ranges using lexical search, symbol lookup, references, and
  migration-specific signals.
- Preserve stable citations as `path:startLine-endLine` so the agent can request
  neighboring or missing ranges.
- Cache file hashes, outlines, and chunks; invalidate only changed files.
- Reserve separate token budgets for system policy, conversation, plan,
  retrieved context, tool results, and output.
- Summarize older tool results without discarding paths, symbols, decisions, or
  unresolved validation failures.
- Refuse binary, generated, secret, and over-limit files unless a policy
  explicitly permits them.

For a huge single file, the agent first reads its outline and relevant regions,
then expands around referenced symbols. For a huge repository, it starts with
manifests, entry points, dependency signals, selected scope, and search results.

## Multi-File Selection and Scope

The frontend supports checkbox selection for multiple files. The production
scope model extends this to:

- Include files, directories, glob-like groups, and saved scope presets.
- Mark scope as `strict` (do not leave selected files) or `guided` (allow
  exploration of related files and report every expansion).
- Distinguish pinned context from editable scope.
- Display estimated file count, byte size, languages, and context cost before a
  run.
- Keep generated/build output and detected secrets excluded by default.
- Let the agent suggest related files before editing them.

Migration work should default to guided scope because imports, configuration,
tests, templates, and call sites commonly live outside the initially selected
files.

## Migration Workflow

A migration run has explicit phases:

1. **Discover:** identify frameworks, versions, manifests, build/test commands,
   architecture, and affected dependency edges.
2. **Plan:** create ordered migration batches with assumptions, risk, and
   validation for each batch.
3. **Transform:** apply small coherent edits in the proposal workspace. Prefer
   syntax-aware transformations when reliable; use targeted patches otherwise.
4. **Inspect:** re-read edits and compare them with neighboring patterns.
5. **Validate:** run the least expensive checks first, then focused tests,
   type-checks, lint, build, and broader tests as approved.
6. **Repair:** feed concise failure evidence back into the agent and iterate.
7. **Review:** group diffs by migration batch and explain behavior changes,
   uncertain areas, skipped files, and remaining manual work.
8. **Apply:** selectively apply accepted hunks after stale-content checks.

Runs are resumable. A large migration is checkpointed into batches so a model or
SSO failure does not lose completed proposals and review decisions.

## Tooling Standard

All tools have typed JSON schemas, normalized outputs, timeouts, size limits,
workspace confinement, audit events, and policy classification.

Minimum read tools:

- `list_directory`, `file_metadata`, `read_file_range`
- `search_text`, `find_files`, `outline_symbols`, `find_references`
- `git_status`, `git_diff`, `git_log` when Git is available

Minimum edit tools:

- `create_file`, `apply_patch`, `rename_file`, `delete_file`
- `format_files` using project-approved formatters
- All edits target an isolated proposal workspace before review.

Large-file editing uses bounded line-range reads followed by exact line-range
replacement. The proposal layer keeps the original hash and produces a diff;
it does not require sending the whole file to the model.

Minimum validation tools:

- `detect_commands`, `run_typecheck`, `run_lint`, `run_tests`, `run_build`
- Arbitrary shell execution is a separate opt-in permission, not an implicit
  capability of the model.

The model cannot invent tools, escape the workspace root, silently widen write
scope, approve its own changes, or bypass limits.

The agent may propose a new constrained transformation when registered tools are
insufficient. A one-run tool requires code-and-scope approval before execution;
a persistent tool additionally requires installation approval and is stored
under the configured filesystem state directory. Both operate on in-memory text
maps without imports, shell, network, environment, or direct filesystem access,
and their outputs enter the normal diff-review flow.

## Review Model

Each proposal stores:

- Base workspace path and file hashes
- Requested and expanded scope
- Agent plan and tool event timeline
- Original and proposed contents
- Unified and side-by-side diffs
- File/hunk review decisions
- Validation commands, exit codes, and bounded output
- Apply journal and rollback data

Review supports accept/reject per file and per hunk, accept all, revise, discard,
conflict warnings, sensitive-file warnings, and a final impact summary. If a
source file changes after proposal generation, apply stops for that file rather
than overwriting newer work.

## AWS Bedrock Boundary

- Angular never receives AWS credentials, profiles, or SSO tokens.
- FastAPI creates `boto3.Session` from `AWS_PROFILE` and `AWS_REGION`.
- Claude Sonnet 4.5 defaults to
  `anthropic.claude-sonnet-4-5-20250929-v1:0` and remains configurable.
- The agent uses Bedrock Converse/ConverseStream with typed tool schemas.
- Expired SSO produces a clear `aws sso login --profile ...` recovery message.
- Model requests, tokens, latency, tool usage, and errors are metered without
  logging credentials or unredacted secret content.

## Non-Functional Requirements

- Cancellation is effective between model and tool steps.
- Runs have configurable step, wall-time, tool-output, file-size, and token
  limits.
- API operations are idempotent where retry is expected.
- Proposal and apply state is durable in a configured local state directory,
  not process memory.
- File writes are atomic and rollback-capable.
- Streaming reconnects from the last durable event ID.
- The backend remains usable without Git.
- No workspace content is sent until the user connects a path and starts a run.
