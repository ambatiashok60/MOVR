"""Conversation compaction preserves goal + retains recent turns (§12)."""

from __future__ import annotations

from app.config import settings
from app.context.compaction_service import CompactionService
from app.models.enums import AgentMode
from app.persistence.database import get_database
from app.persistence.repositories import ConversationRepository, MessageRepository


def _seed(conv_repo, msg_repo, conv_id, n_turns):
    for i in range(n_turns):
        msg_repo.add(conv_id, "user", f"user message {i} about status")
        msg_repo.add(conv_id, "assistant", f"assistant reply {i} discovered finding {i}")


def test_no_compaction_below_threshold(workspace):
    db = get_database()
    conv_repo, msg_repo = ConversationRepository(db), MessageRepository(db)
    conv = conv_repo.create(str(workspace), AgentMode.AGENT)
    _seed(conv_repo, msg_repo, conv.id, settings.compaction_trigger_turns - 1)

    ctx = CompactionService(conv_repo, msg_repo).compact_if_required(conv.id)
    assert ctx.compacted is False
    assert ctx.summary is None


def test_compaction_preserves_goal_and_recent(workspace):
    db = get_database()
    conv_repo, msg_repo = ConversationRepository(db), MessageRepository(db)
    conv = conv_repo.create(str(workspace), AgentMode.AGENT)
    _seed(conv_repo, msg_repo, conv.id, settings.compaction_trigger_turns + 4)

    ctx = CompactionService(conv_repo, msg_repo).compact_if_required(conv.id)
    assert ctx.compacted is True
    assert ctx.summary is not None
    assert ctx.summary.goal  # goal preserved
    assert ctx.recent_turns_retained == settings.recent_turns_to_keep
    # the active summary is persisted on the conversation
    assert conv_repo.get(conv.id).active_summary_id is not None
    assert conv_repo.get(conv.id).compaction_count == 1
