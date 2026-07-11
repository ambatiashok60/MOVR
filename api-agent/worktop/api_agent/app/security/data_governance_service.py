from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field
from worktop.api_agent.app.utils.logging_utils import log_step

FileClassification = Literal["safe", "internal", "sensitive", "restricted"]

_RESTRICTED_NAMES = {
    ".env", ".env.local", ".env.production", ".env.staging", ".npmrc", ".netrc",
    ".pgpass", "credentials", "credentials.json", "service-account.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
}
_RESTRICTED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
_SENSITIVE_HINTS = ("secret", "credential", "private", "token", "certs")
_INTERNAL_SUFFIXES = (".yml", ".yaml", ".json", ".toml", ".ini", ".conf")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key)\b(\s*[:=]\s*)(['\"]?)([^\s'\"]{6,})"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)


class DataGovernanceAudit(BaseModel):
    files_sent: list[str] = Field(default_factory=list)
    files_blocked: list[str] = Field(default_factory=list)
    chars_sent: int = 0
    redactions: int = 0


class DataGovernanceService:
    """The mandatory gate between repository content and model-facing tools."""

    def __init__(self) -> None:
        self.audit = DataGovernanceAudit()

    def classify(self, path: str) -> FileClassification:
        name = PurePosixPath(path).name.lower()
        lowered = path.lower()
        if name in _RESTRICTED_NAMES or name.startswith(".env") or name.endswith(_RESTRICTED_SUFFIXES):
            return "restricted"
        if any(hint in lowered for hint in _SENSITIVE_HINTS):
            return "sensitive"
        if name.endswith(_INTERNAL_SUFFIXES):
            return "internal"
        return "safe"

    def release_file(self, path: str, content: str) -> str | None:
        if self.classify(path) == "restricted":
            self.audit.files_blocked.append(path)
            log_step("api_repository_file_blocked", {"path": path, "classification": "restricted"})
            return None
        redactions = 0
        for pattern in _SECRET_PATTERNS:
            def replace(match: re.Match[str]) -> str:
                nonlocal redactions
                redactions += 1
                if match.lastindex and match.lastindex >= 4:
                    return f"{match.group(1)}{match.group(2)}{match.group(3)}[REDACTED]"
                return "[REDACTED]"
            content = pattern.sub(replace, content)
        self.audit.files_sent.append(path)
        self.audit.chars_sent += len(content)
        self.audit.redactions += redactions
        log_step(
            "api_repository_file_released",
            {"path": path, "classification": self.classify(path), "chars": len(content), "redactions": redactions},
        )
        return content
