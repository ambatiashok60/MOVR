"""Rolling-memory conversation compaction (§12).

Deterministic and LLM-free so it runs identically under FakeLLM and in tests.
Incremental: previous summary + newly-eligible older turns -> updated summary.
It never deletes stored messages; it only shapes what the model receives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.models.conversation import ConversationSummary
from app.persistence.repositories import ConversationRepository, MessageRepository


@dataclass
class ConversationContext:
    summary: ConversationSummary | None = None
    recent_turns: list[dict] = field(default_factory=list)
    compacted: bool = False
    compacted_through_turn: int = 0
    recent_turns_retained: int = 0


class CompactionService:
    def __init__(self, conversations: ConversationRepository, messages: MessageRepository) -> None:
        self._conversations = conversations
        self._messages = messages

    def compact_if_required(self, conversation_id: str) -> ConversationContext:
        turns = self._messages.get_turns(conversation_id)

        if len(turns) < settings.compaction_trigger_turns:
            return ConversationContext(summary=None, recent_turns=turns,
                                       recent_turns_retained=len(turns))

        keep = settings.recent_turns_to_keep
        older, recent = turns[:-keep], turns[-keep:]
        existing = self._conversations.get_active_summary(conversation_id)
        summary = self._merge(existing, older)
        self._conversations.save_summary(conversation_id, summary)

        conv = self._conversations.get(conversation_id)
        if conv:
            self._conversations.touch(conversation_id, compaction_count=conv.compaction_count + 1)

        return ConversationContext(
            summary=summary, recent_turns=recent, compacted=True,
            compacted_through_turn=len(older), recent_turns_retained=len(recent),
        )

    @staticmethod
    def _merge(existing: ConversationSummary | None, older: list[dict]) -> ConversationSummary:
        summary = existing.model_copy(deep=True) if existing else ConversationSummary()
        if not summary.goal and older:
            summary.goal = older[0].get("user", "")[:200]

        for turn in older:
            user = (turn.get("user") or "").strip()
            assistant = (turn.get("assistant") or "").strip()
            if user:
                _append_unique(summary.decisions, f"User asked: {user[:120]}")
            if assistant:
                _append_unique(summary.architectural_findings, assistant[:160])

        summary.current_plan_summary = (
            f"{len(older)} earlier turns compacted; goal preserved."
        )
        # Keep bounded so the summary never grows without limit.
        summary.decisions = summary.decisions[-20:]
        summary.architectural_findings = summary.architectural_findings[-20:]
        return summary


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
