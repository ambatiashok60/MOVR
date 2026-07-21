"""Pure helpers for building the agent's per-turn context.

Kept free of AWS imports so they stay unit-testable without boto3.
"""
from __future__ import annotations


def to_converse_history(messages: list[dict], limit: int, max_chars: int) -> list[dict]:
    """Map stored session messages to bounded Bedrock converse history.

    Keeps the most recent `limit` messages within a total character budget so
    long sessions cannot blow the context. Roles must alternate for converse;
    consecutive same-role messages are merged and a leading assistant message
    is dropped.
    """
    recent = [
        m for m in messages[-limit:]
        if m.get("role") in {"user", "assistant"} and (m.get("content") or "").strip()
    ]
    budget = max_chars
    kept: list[dict] = []
    for message in reversed(recent):
        text = str(message["content"])[:max_chars]
        if budget - len(text) < 0 and kept:
            break
        budget -= len(text)
        kept.append({"role": message["role"], "text": text})
    kept.reverse()
    result: list[dict] = []
    for message in kept:
        if result and result[-1]["role"] == message["role"]:
            result[-1]["content"][0]["text"] += "\n\n" + message["text"]
        else:
            result.append({"role": message["role"], "content": [{"text": message["text"]}]})
    if result and result[0]["role"] == "assistant":
        result.pop(0)
    return result


def unfinished_plan(plan: list[dict] | None) -> list[dict]:
    """Return the plan only when it still has work left to resume."""
    steps = plan or []
    if any(step.get("status") in {"pending", "in_progress"} for step in steps):
        return steps
    return []


def compacted_history(messages: list[dict], limit: int, max_chars: int) -> tuple[list[dict], dict]:
    """Bound history and preserve a compact trace of older decisions when needed."""
    eligible = [m for m in messages if m.get("role") in {"user", "assistant"} and (m.get("content") or "").strip()]
    raw_chars = sum(len(str(item.get("content", ""))) for item in eligible)
    if len(eligible) <= limit and raw_chars <= max_chars:
        history = to_converse_history(eligible, limit, max_chars)
        return history, {"compacted": False, "estimatedTokens": sum(len(str(item)) for item in history) // 4}
    recent_count = max(2, limit - 2)
    older, recent = eligible[:-recent_count], eligible[-recent_count:]
    summary_lines = []
    for item in older[-12:]:
        content = " ".join(str(item.get("content", "")).split())[:240]
        summary_lines.append(f"- {item['role']}: {content}")
    summary = "<conversation_summary>\nEarlier decisions and findings:\n" + "\n".join(summary_lines) + "\n</conversation_summary>"
    synthesized = [
        {"role": "user", "content": summary},
        {"role": "assistant", "content": "I will preserve these earlier decisions while continuing."},
        *recent,
    ]
    history = to_converse_history(synthesized, limit, max_chars)
    return history, {
        "compacted": True, "messagesCompacted": len(older),
        "estimatedTokens": sum(len(str(item)) for item in history) // 4,
    }
