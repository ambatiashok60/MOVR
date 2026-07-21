"""Semantic response batching contracts (§13/§15)."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ResponseBatchType


class ResponseSection(BaseModel):
    """One entry in the pre-generation section manifest."""

    type: ResponseBatchType
    title: str | None = None


class ResponseBatch(BaseModel):
    batch_id: str
    run_id: str
    index: int
    type: ResponseBatchType
    title: str | None = None
    markdown: str = ""
    is_final: bool = False
