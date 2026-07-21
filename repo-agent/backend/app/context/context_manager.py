"""Facade the orchestrator uses to prepare conversation context for a run."""

from __future__ import annotations

from app.context.compaction_service import CompactionService, ConversationContext
from app.persistence.repositories import ConversationRepository, MessageRepository


class ContextManager:
    def __init__(self, conversations: ConversationRepository, messages: MessageRepository) -> None:
        self._compaction = CompactionService(conversations, messages)

    def prepare_conversation(self, conversation_id: str) -> ConversationContext:
        return self._compaction.compact_if_required(conversation_id)
