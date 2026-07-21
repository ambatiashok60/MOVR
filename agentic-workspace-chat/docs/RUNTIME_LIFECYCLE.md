# Runtime lifecycle and freeze prevention

This is the operational contract for the local application. It describes what
the user should see, which process owns each step, and how every wait terminates.

## Simple expected flow

1. Start FastAPI on `localhost:8000` and Angular on `localhost:4200`.
2. Angular calls `/api/health`, then `/api/config`, and shows **Backend connected**.
3. Connect a workspace. The backend validates its allowed root and returns a
   bounded file list; the UI shows `validating`, `loading`, then `connected`.
4. Send a prompt. The UI shows one working indicator and disables duplicate send.
5. The backend runs the bounded Bedrock/tool loop in a worker thread.
6. The completed response returns the answer, plan, evidence, proposed actions,
   and reviewed file-change proposal in one payload.
7. The UI always leaves its busy state on success, error, timeout, or Stop.

The current implementation is request/response, not token streaming. Silence
during a request means the bounded agent is working; it must not mean an
unlimited wait.

## Dead-hang controls

| Boundary | Limit/recovery |
|---|---|
| Backend health/config | UI timeout after 5 seconds with Retry |
| Workspace validation | UI timeout after 15 seconds |
| Workspace file discovery | UI timeout after 30 seconds |
| Agent request | Backend `REQUEST_TIMEOUT_SECONDS`; UI adds a 10-second transport margin |
| Bedrock connection | `BEDROCK_CONNECT_TIMEOUT_SECONDS` |
| Bedrock response read | `BEDROCK_READ_TIMEOUT_SECONDS` |
| Browser Stop/navigation | HTTP unsubscribe; backend detects disconnect and signals cancellation |
| Agent loop | bounded steps, response continuations, tool runs, output sizes, and tool timeouts |

An in-flight boto call cannot be force-killed safely by `asyncio`; after client
disconnect the HTTP handler returns immediately while the detached worker exits
at the next provider/tool boundary. Late results are consumed and discarded,
and workspace edits are still only proposals.

## Connectivity diagnosis

- **Backend unavailable:** check `curl http://localhost:8000/api/health` and the
  FastAPI terminal. The Angular proxy must target port 8000.
- **Workspace stays loading:** inspect `/api/workspaces/files`; reduce
  `WORKSPACE_MAX_FILES` or narrow the selected root for very large repositories.
- **Agent times out:** inspect the request ID and backend log, AWS SSO validity,
  region/model access, and Bedrock read timeout. Retry only after the cause is known.
- **Stop appears slow:** the browser should become interactive immediately. A
  boto worker can remain briefly in backend logs until its network read returns.
- **UI itself is unresponsive:** capture browser performance data; very large
  file trees or Markdown/diffs may require virtualization or worker-based parsing.

## Deliberate non-goals

This hardening does not add SSE/token streaming, a distributed job queue, or
forceful thread termination. Those require a run-ID-based asynchronous API and
worker lifecycle rather than more complexity inside the current HTTP endpoint.
