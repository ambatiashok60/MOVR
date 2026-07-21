from app.session_store import SessionStore


def test_manual_compaction_archives_raw_history_and_keeps_recent_messages(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("/workspace")
    for index in range(10):
        store.append(session["id"], {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"})

    result = store.compact(session["id"], keep=4)

    assert result == {"compacted": 6, "remaining": 6}
    assert "message 9" in store.messages(session["id"])[-1]["content"]
    assert list((store.root / session["id"]).glob("messages.precompact-*.jsonl"))
