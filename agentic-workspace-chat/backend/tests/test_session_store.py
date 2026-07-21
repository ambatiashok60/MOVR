def test_filesystem_session_store_round_trip(tmp_path):
    from app.session_store import SessionStore

    store = SessionStore(tmp_path)
    session = store.create("/tmp/workspace")
    store.append(session["id"], {"role": "user", "content": "hello"})

    assert store.list()[0]["id"] == session["id"]
    assert store.messages(session["id"])[0]["content"] == "hello"
