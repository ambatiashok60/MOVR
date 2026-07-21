"""Normalizes tool results into short observation strings for the loop/LLM."""

from __future__ import annotations

from app.models.tool import ToolResult


class ObservationManager:
    def normalize(self, result: ToolResult) -> str:
        head = f"[{result.tool_name}] {result.summary}"
        if result.truncated:
            head += " (truncated)"
        if result.content:
            snippet = result.content.strip().splitlines()[:4]
            head += "\n" + "\n".join(snippet)
        return head[:1200]
