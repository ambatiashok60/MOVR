from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

_BLOCKED = {".env", ".npmrc", ".netrc", "credentials.json", "service-account.json", "id_rsa", "id_ed25519"}
_BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
_SECRETS = (
    re.compile(r"(?i)\b(password|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b(\s*[:=]\s*)(['\"]?)([^\s'\"]{6,})"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk-|gh[pousr]_)[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)

@dataclass
class DataGovernanceAudit:
    files_released: list[str] = field(default_factory=list)
    files_blocked: list[str] = field(default_factory=list)
    redactions: int = 0
    characters_released: int = 0

class DataGovernanceService:
    def __init__(self) -> None:
        self.audit = DataGovernanceAudit()

    def blocked(self, path: str) -> bool:
        name = PurePosixPath(path).name.lower()
        return name in _BLOCKED or name.startswith(".env") or name.endswith(_BLOCKED_SUFFIXES)

    def release(self, path: str, content: str) -> str | None:
        if self.blocked(path):
            self.audit.files_blocked.append(path)
            return None
        redactions = 0
        for pattern in _SECRETS:
            def replace(match: re.Match[str]) -> str:
                nonlocal redactions
                redactions += 1
                if match.lastindex and match.lastindex >= 4:
                    return f"{match.group(1)}{match.group(2)}{match.group(3)}[REDACTED]"
                return "[REDACTED]"
            content = pattern.sub(replace, content)
        self.audit.files_released.append(path)
        self.audit.redactions += redactions
        self.audit.characters_released += len(content)
        return content
