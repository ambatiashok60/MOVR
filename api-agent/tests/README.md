# API Agent Test Plan

Automated tests are not fully implemented yet. This folder should cover the
backend before UI integration.

Priority test groups:

```text
strategy selection
  Java Spring MockMvc
  Java Spring RestAssured
  Python FastAPI TestClient
  Python pytest/httpx

team strategy discovery
  Java repo profile detection
  Python repo profile detection
  fixture/auth/client helper detection
  CI/stage command discovery

mock/stub planning
  Mockito/@MockBean style controller dependencies
  WireMock downstream stubs
  FastAPI dependency overrides
  respx/responses/pytest-mock outbound HTTP stubs

generation output
  CI and stage file path selection
  strategy metadata returned in result
  reused examples and source snippets returned in result

validation
  dry-run command resolution
  missing generated file detection
```

The local base Python environment used during scaffolding did not include
`pydantic` or `fastapi`, so current verification is limited to:

```bash
python3 -m compileall -q api-agent/app
```
