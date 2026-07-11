"""PLACEHOLDER — do not use as-is.

Same caveat as db.py: DefaultLLMClient already receives a `tenant_id`, so tenant resolution
already exists somewhere in the current app (most likely from an auth middleware / JWT claim).
On integration: delete this and import the real tenant-resolution dependency.
"""

from fastapi import Header


def get_tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    # Standalone scaffold fallback. On host integration, replace this dependency with the
    # platform's real tenant/auth resolution.
    return x_tenant_id or "local-dev"
