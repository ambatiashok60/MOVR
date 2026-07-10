from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

from app.logging_config import log_event

logger = logging.getLogger(__name__)

FileClassification = Literal["safe", "internal", "sensitive", "restricted"]

_RESTRICTED_NAMES = {
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    ".npmrc", ".netrc", ".pgpass", "credentials", "credentials.json",
    "service-account.json", "id_rsa", "id_ed25519", "id_ecdsa",
}
_RESTRICTED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".crt", ".cer")
_SENSITIVE_PATH_HINTS = ("secret", "credential", "private", "token", "certs")
_INTERNAL_SUFFIXES = (".yml", ".yaml", ".json", ".toml", ".ini", ".conf", ".config.js", ".config.ts")

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key)\b(\s*[:=]\s*)(['\"]?)([^\s'\"]{6,})"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    re.compile(r"\b(eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)
_REDACTION = "[REDACTED]"


class RedactionResult(BaseModel):
    content: str
    redactions: int = 0


class DataGovernanceAudit(BaseModel):
    """What repository data left the boundary toward the LLM, and how much
    sensitive material was removed before it did."""

    files_sent: list[str] = Field(default_factory=list)
    files_blocked: list[str] = Field(default_factory=list)
    chars_sent: int = 0
    redactions: int = 0


class DataGovernanceService:
    """Classify repository files and scrub secrets before anything reaches an LLM.

    Restricted files (env files, key material, credential stores) are never
    sent at all; sensitive and internal content is redacted pattern-by-pattern;
    every file that crosses the boundary is recorded in an audit.
    """

    def __init__(self) -> None:
        self.audit = DataGovernanceAudit()

    def classify(self, path: str) -> FileClassification:
        name = PurePosixPath(path).name.lower()
        lowered = path.lower()
        if name in _RESTRICTED_NAMES or name.endswith(_RESTRICTED_SUFFIXES):
            return "restricted"
        if name.startswith(".env"):
            return "restricted"
        if any(hint in lowered for hint in _SENSITIVE_PATH_HINTS):
            return "sensitive"
        if name.endswith(_INTERNAL_SUFFIXES):
            return "internal"
        return "safe"

    def is_blocked(self, path: str) -> bool:
        return self.classify(path) == "restricted"

    def redact(self, content: str) -> RedactionResult:
        redactions = 0
        for pattern in _SECRET_PATTERNS:
            def substitute(match: re.Match[str]) -> str:
                nonlocal redactions
                redactions += 1
                if match.lastindex and match.lastindex >= 4:
                    return (
                        f"{match.group(1)}{match.group(2)}{match.group(3)}{_REDACTION}"
                    )
                return _REDACTION

            content = pattern.sub(substitute, content)
        return RedactionResult(content=content, redactions=redactions)

    def release_file(self, path: str, content: str) -> str | None:
        """Gate one file on its way to an LLM prompt.

        Returns redacted content, or None when the file is restricted and must
        not be sent in any form. Every decision is audited.
        """
        if self.is_blocked(path):
            self.audit.files_blocked.append(path)
            log_event(
                logger,
                logging.WARNING,
                "data_governance",
                "file_blocked",
                path=path,
                classification="restricted",
            )
            return None
        result = self.redact(content)
        self.audit.files_sent.append(path)
        self.audit.chars_sent += len(result.content)
        self.audit.redactions += result.redactions
        if result.redactions:
            log_event(
                logger,
                logging.WARNING,
                "data_governance",
                "content_redacted",
                path=path,
                classification=self.classify(path),
                redactions=result.redactions,
            )
        return result.content
