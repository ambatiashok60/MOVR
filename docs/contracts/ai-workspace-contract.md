# AI Workspace — Frontend ⇄ Backend Contract (demo notes)

The AI Workspace feature is already a full pair: Angular app at
`ai-workspace/frontend` (route `/ai-workspace`) and FastAPI backend at
`ai-workspace/backend` (`uvicorn app.main:app --port 8000` from
`ai-workspace/backend`; OpenAPI at `/docs`, prefix `/api`).

## Route groups (see /docs for full schemas)

- `bootstrap` — one call returning workspace/session/models/tools/prompts.
- `workspace` — validate path, tree, repositories/branches.
- `sessions` — CRUD + messages (SQLite persistence by default).
- `execution` — start Ask/Agent run, SSE timeline (`/sse/...`), abort.
- `review` — proposed file changes, keep/reject decisions, apply
  (transactional: lock, snapshot, journal, rollback, stale-proposal check).
- `models`, `tools` — catalogs; tool availability differs by mode
  (Ask: read-only tools; Agent: adds write/run — enforced server-side).

## Running for a demo without WorkTop

```bash
cd ai-workspace/backend
AI_WORKSPACE_ALLOW_MOCK_LLM=true uvicorn app.main:app --port 8000
cd ../frontend && npm start   # proxies /api → :8000
```

`AI_WORKSPACE_ALLOW_MOCK_LLM=true` swaps in `MockLLMClient` (canned
responses) only when the real WorkTop `DefaultLLMClient` is unavailable —
enough to click through Ask/Agent flows, timeline, and the review panel.
For real answers the backend needs `worktop.core_services` importable.
