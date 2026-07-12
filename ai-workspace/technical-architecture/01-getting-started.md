# Getting started

AI Workspace provides repository-aware Ask and Agent modes. Ask returns evidence-backed guidance
without changing files. Agent discovers the repository, plans work, uses bounded tools, stages file
changes, validates them and waits for review before transactional Apply.

## Runtime

- Backend: Python 3.11+, FastAPI 0.110+, Pydantic 2.6+, pydantic-settings 2.2+
- Frontend: Node 20, Angular 18.2, PrimeNG 18, PrimeIcons 7, RxJS 7.8, TypeScript 5.5

The local Node 14 installation is unsupported; use the Node 20 devcontainer, GitHub Actions or another
Node 20 environment for preview validation.

Preview configuration explicitly allows the mock model and memory state. Production must disable the
mock, select durable state, inject authenticated host dependencies, and configure an isolated
workspace. See `PREVIEW.md` for the combined API Tests and AI Workspace browser preview.
