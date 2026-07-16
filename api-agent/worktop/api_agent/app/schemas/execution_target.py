from __future__ import annotations

from enum import StrEnum


class ExecutionTarget(StrEnum):
    CI = "ci"
    STAGE = "stage"
    BOTH = "both"
