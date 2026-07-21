"""Credential-error classification for the Bedrock retry/reauth flow.

boto3/botocore are optional. When they are not installed we still expose a
classifier that works on error *codes*, so the logic is unit-testable without
the AWS SDK present.
"""

from __future__ import annotations

# Error codes that indicate an expired/invalid session and warrant a
# session reset + retry (and possibly `aws sso login`).
CREDENTIAL_ERROR_CODES = frozenset({
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "AccessDeniedException",
    "UnauthorizedSSOTokenError",
})

# botocore exception *type names* that mean the same thing. Matched by name so
# we do not need to import botocore at module load.
CREDENTIAL_ERROR_TYPES = frozenset({
    "CredentialRetrievalError",
    "UnauthorizedSSOTokenError",
    "NoCredentialsError",
    "SSOTokenLoadError",
    "TokenRetrievalError",
})


class LLMConfigurationError(RuntimeError):
    """Raised when a provider is requested but not usable (e.g. boto3 missing)."""


def _error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return response.get("Error", {}).get("Code")
    return None


def is_credential_error(exc: Exception) -> bool:
    if type(exc).__name__ in CREDENTIAL_ERROR_TYPES:
        return True
    code = _error_code(exc)
    return code in CREDENTIAL_ERROR_CODES if code else False
