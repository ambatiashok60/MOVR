# Getting started

API Agent creates API scenarios from a story and turns an approved scenario into repository-native
integration-test code, including supporting mocks or stubs when repository evidence supports them.

## Runtime

- Backend: Python 3.11+, FastAPI 0.111+, Pydantic 2.7+, pytest 8+
- Portable preview: Node 20, Angular 18.2, PrimeNG 18, RxJS 7.8, TypeScript 5.5

```bash
cd api-agent
python -m pytest
```

For host integration, mount the API router, inject authenticated tenant/DB/model dependencies, and
copy or package `frontend/test-generation` into the compatible Angular host. Start with mocks, verify
the UI contract, then switch the DI providers and API prefix to the real backend.

Two entry points must remain separate: story-to-scenarios explores coverage; scenario-to-code acts on
one reviewed scenario and current repository state.
