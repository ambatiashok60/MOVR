from enum import Enum


class ReviewDecision(str, Enum):
    PENDING = "pending"
    KEPT = "kept"
    REJECTED = "rejected"
