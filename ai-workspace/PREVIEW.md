# Run The Combined Preview

## Backend

From `ai-workspace/backend`:

```bash
AI_WORKSPACE_ALLOW_MOCK_LLM=true \
AI_WORKSPACE_STATE_BACKEND=memory \
AI_WORKSPACE_WORKSPACE_ROOT_ALLOWLIST='["/Users/ashokkumar/Documents/movr/MOVR"]' \
python -m uvicorn worktop.ai_workspace.app.main:app --host 127.0.0.1 --port 8000
```

## Frontend

From `ai-workspace/frontend`, using Node 18+:

```bash
pnpm start -- --proxy-config proxy.conf.json
```

Open:

```text
http://127.0.0.1:4200/test-generation
http://127.0.0.1:4200/ai-workspace
```

API Test Generation uses in-browser mocks by default. AI Workspace uses the real FastAPI routes
with the explicit mock LLM, allowing Ask, Agent proposal, diff review, Keep/Reject, and Apply to be
demonstrated without Worktop model configuration.
