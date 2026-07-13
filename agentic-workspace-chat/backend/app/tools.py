from dataclasses import dataclass, field
from pathlib import Path
from fastapi import HTTPException

from .config import Settings
from .custom_runtime import CustomToolStore, ToolProposal, execute_code
from .models import FileChange
from .workspace import files, read_text, resolve_file, sha


def spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"toolSpec": {"name": name, "description": description, "inputSchema": {
        "json": {"type": "object", "properties": properties, "required": required}
    }}}


TOOL_CONFIG = {"tools": [
    spec("list_files", "List workspace files. Use this to discover structure.", {
        "query": {"type": "string", "description": "Optional case-insensitive path filter"},
    }, []),
    spec("search_text", "Search text files and return matching lines with paths and line numbers.", {
        "query": {"type": "string"},
        "path": {"type": "string", "description": "Optional directory or file prefix"},
    }, ["query"]),
    spec("read_file", "Read an exact line range from a text file.", {
        "path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    }, ["path"]),
    spec("replace_in_file", "Propose a precise replacement in an existing text file. old_text must occur exactly once.", {
        "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
    }, ["path", "old_text", "new_text"]),
    spec("create_file", "Propose a new text file with the appropriate extension and complete content.", {
        "path": {"type": "string"}, "content": {"type": "string"},
    }, ["path", "content"]),
    spec("delete_file", "Propose deletion of an existing file only when required by the task.", {
        "path": {"type": "string"},
    }, ["path"]),
    spec("propose_ephemeral_tool", "Propose a one-run constrained Python transformation when built-in tools are insufficient. Execution requires user approval.", {
        "name": {"type": "string"}, "description": {"type": "string"},
        "code": {"type": "string", "description": "Define transform(files, args) returning {path: text_or_null}. No imports."},
        "input_paths": {"type": "array", "items": {"type": "string"}}, "args": {"type": "object"},
    }, ["name", "description", "code", "input_paths"]),
    spec("propose_persistent_tool", "Propose a reusable constrained transformation tool. Installation requires user approval.", {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{2,40}$"}, "description": {"type": "string"},
        "code": {"type": "string", "description": "Define transform(files, args) returning {path: text_or_null}. No imports."},
    }, ["name", "description", "code"]),
]}


@dataclass
class ToolRunner:
    root: Path
    config: Settings
    overlays: dict[str, str | None] = field(default_factory=dict)
    originals: dict[str, str] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    action_proposals: list[ToolProposal] = field(default_factory=list)

    def tool_config(self) -> dict:
        tools = list(TOOL_CONFIG["tools"])
        for installed in CustomToolStore(self.config).installed():
            manifest = installed["manifest"]
            tools.append(spec(manifest["name"], manifest["description"], {
                "paths": {"type": "array", "items": {"type": "string"}},
                "args": {"type": "object"},
            }, ["paths"]))
        return {"tools": tools}

    def _content(self, path: str) -> str:
        if path in self.overlays:
            content = self.overlays[path]
            if content is None:
                raise ValueError(f"{path} is proposed for deletion")
            return content
        return read_text(self.root, path, self.config.workspace_max_file_bytes)

    def _remember(self, path: str) -> str:
        if path not in self.originals:
            target = resolve_file(self.root, path)
            self.originals[path] = target.read_text() if target.exists() else ""
        return self.originals[path]

    def execute(self, name: str, data: dict) -> dict:
        try:
            method = getattr(self, f"tool_{name}", None)
            result = method(**data) if method else self._execute_installed(name, data)
            self.events.append({"tool": name, "input": data, "status": "success"})
            return result
        except (HTTPException, OSError, UnicodeError, ValueError) as error:
            detail = error.detail if isinstance(error, HTTPException) else str(error)
            self.events.append({"tool": name, "input": data, "status": "error", "error": str(error)})
            return {"error": detail}

    def tool_list_files(self, query: str = "") -> dict:
        found = files(self.root, self.config.workspace_max_files)
        if query:
            found = [path for path in found if query.lower() in path.lower()]
        return {"files": found[:500], "truncated": len(found) > 500}

    def tool_search_text(self, query: str, path: str = "") -> dict:
        matches: list[dict] = []
        for relative in files(self.root, self.config.workspace_max_files):
            if path and not relative.startswith(path):
                continue
            try:
                content = self._content(relative)
            except Exception:
                continue
            for number, line in enumerate(content.splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append({"path": relative, "line": number, "text": line[:500]})
                    if len(matches) == 200:
                        return {"matches": matches, "truncated": True}
        return {"matches": matches, "truncated": False}

    def tool_read_file(self, path: str, start_line: int = 1, end_line: int = 400) -> dict:
        lines = self._content(path).splitlines()
        start = max(1, start_line)
        end = min(len(lines), max(start, end_line), start + 499)
        return {"path": path, "startLine": start, "endLine": end, "totalLines": len(lines),
                "content": "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))}

    def tool_replace_in_file(self, path: str, old_text: str, new_text: str) -> dict:
        content = self._content(path)
        count = content.count(old_text)
        if count != 1:
            raise ValueError(f"old_text must match exactly once in {path}; found {count}")
        self._remember(path)
        self.overlays[path] = content.replace(old_text, new_text, 1)
        return {"proposed": path, "operation": "update"}

    def tool_create_file(self, path: str, content: str) -> dict:
        target = resolve_file(self.root, path)
        if target.exists() or path in self.overlays:
            raise ValueError(f"{path} already exists; use replace_in_file")
        self._remember(path)
        self.overlays[path] = content
        return {"proposed": path, "operation": "create"}

    def tool_delete_file(self, path: str) -> dict:
        self._content(path)
        self._remember(path)
        self.overlays[path] = None
        return {"proposed": path, "operation": "delete"}

    def tool_propose_ephemeral_tool(self, name: str, description: str, code: str,
                                    input_paths: list[str], args: dict | None = None) -> dict:
        proposal = CustomToolStore(self.config).proposal(name, description, code, input_paths, args or {})
        self.action_proposals.append(proposal)
        return {"actionProposalId": proposal.id, "status": "awaiting_user_approval"}

    def tool_propose_persistent_tool(self, name: str, description: str, code: str) -> dict:
        proposal = CustomToolStore(self.config).proposal(name, description, code, [], {}, persistent=True)
        self.action_proposals.append(proposal)
        return {"actionProposalId": proposal.id, "status": "awaiting_user_approval"}

    def _execute_installed(self, name: str, data: dict) -> dict:
        installed = next((tool for tool in CustomToolStore(self.config).installed()
                          if tool["manifest"]["name"] == name), None)
        if not installed:
            raise ValueError(f"Unknown tool: {name}")
        paths = data.get("paths", [])
        source = {path: self._content(path) for path in paths}
        output = execute_code(installed["code"], source, data.get("args", {}), self.config.custom_tool_timeout_seconds)
        return self._merge_output(output)

    def run_action(self, proposal: ToolProposal) -> dict:
        source = {path: self._content(path) for path in proposal.input_paths}
        return self._merge_output(execute_code(
            proposal.code, source, proposal.args, self.config.custom_tool_timeout_seconds
        ))

    def _merge_output(self, output: dict[str, str | None]) -> dict:
        for path, content in output.items():
            self._remember(path)
            self.overlays[path] = content
        return {"proposedFiles": list(output)}

    def changes(self) -> list[FileChange]:
        result = []
        for path, content in self.overlays.items():
            original = self.originals[path]
            operation = "delete" if content is None else ("create" if original == "" else "update")
            result.append(FileChange(path=path, content=content, operation=operation, original_sha256=sha(original)))
        return result
