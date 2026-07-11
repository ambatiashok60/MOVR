"""PLACEHOLDER — do not use as-is.

The existing TestGenWorkTop backend already has a `db` session dependency (proven by
DefaultLLMClient's `__init__(self, db, tenant_id)` signature — something is already producing
that `db` object for every other service). This file exists only so
dependencies/ai_workspace_dependencies.py has something to import during development of this
scaffold in isolation.

On integration: delete this file and import the real dependency (commonly something like
`app.dependencies.get_db` or `app.database.session.get_db` in a FastAPI + SQLAlchemy app) —
do not run two separate DB session mechanisms side by side.
"""


def get_db():
    # Standalone scaffold fallback. On host integration, replace this dependency with the
    # platform's real DB session provider instead of using None.
    return None
