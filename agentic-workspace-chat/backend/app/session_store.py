from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class SessionStore:
    def __init__(self, root: Path):
        self.root = root.expanduser()
        if not self.root.is_absolute():
            self.root = Path(__file__).resolve().parents[2] / self.root
        self.root = self.root / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, workspace: str | None = None) -> dict:
        session_id = str(uuid4())
        session = {"id": session_id, "workspace": workspace, "createdAt": self._now(), "updatedAt": self._now()}
        self._write(session_id, "session.json", session)
        self._write(session_id, "messages.jsonl", "")
        return session

    def list(self) -> list[dict]:
        result = []
        for path in self.root.glob("*/session.json"):
            try: result.append(json.loads(path.read_text()))
            except (OSError, json.JSONDecodeError): pass
        return sorted(result, key=lambda item: item.get("updatedAt", ""), reverse=True)

    def append(self, session_id: str, message: dict) -> None:
        path = self.root / session_id / "messages.jsonl"
        if not path.parent.is_dir():
            raise ValueError("Session does not exist")
        with path.open("a") as handle:
            handle.write(json.dumps({**message, "timestamp": self._now()}) + "\n")
        metadata = json.loads((path.parent / "session.json").read_text())
        metadata["updatedAt"] = self._now()
        self._write(session_id, "session.json", metadata)

    def messages(self, session_id: str) -> list[dict]:
        path = self.root / session_id / "messages.jsonl"
        if not path.exists(): return []
        result = []
        for line in path.read_text().splitlines():
            try: result.append(json.loads(line))
            except json.JSONDecodeError: pass
        return result

    def save_execution(self, session_id: str, state: dict) -> None:
        if not (self.root / session_id).is_dir():
            return
        self._write(session_id, "execution.json", {**state, "updatedAt": self._now()})

    def execution(self, session_id: str) -> dict:
        path = self.root / session_id / "execution.json"
        if not path.exists():
            return {"status": "idle", "plan": []}
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return {"status": "unknown", "plan": []}

    def compact(self, session_id: str, keep: int = 6) -> dict:
        messages = self.messages(session_id)
        if len(messages) <= keep:
            return {"compacted": 0, "remaining": len(messages)}
        older, recent = messages[:-keep], messages[-keep:]
        summary = "\n".join(
            f"- {item.get('role', 'unknown')}: {' '.join(str(item.get('content', '')).split())[:240]}"
            for item in older[-20:]
        )
        compacted = [
            {"role": "user", "content": "<conversation_summary>\n" + summary + "\n</conversation_summary>", "timestamp": self._now()},
            {"role": "assistant", "content": "Earlier decisions were compacted; I will preserve them while continuing.", "timestamp": self._now()},
            *recent,
        ]
        directory = self.root / session_id
        archive = directory / f"messages.precompact-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
        archive.write_text("\n".join(json.dumps(item) for item in messages) + "\n")
        self._write(session_id, "messages.jsonl", "\n".join(json.dumps(item) for item in compacted) + "\n")
        return {"compacted": len(older), "remaining": len(compacted)}

    def _write(self, session_id: str, name: str, value: object) -> None:
        directory = self.root / session_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(value if isinstance(value, str) else json.dumps(value, indent=2))
        temporary.replace(path)

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
