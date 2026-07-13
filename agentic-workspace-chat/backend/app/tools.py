from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from fastapi import HTTPException

from .config import Settings
from .custom_runtime import CustomToolStore, ToolProposal, execute_code
from .models import FileChange
from .workspace import files, read_text, resolve_file, sha
from .repository_index import build_index


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
    spec("find_relationships", "Find evidence-backed references to a symbol, route, class, or file across the workspace.", {
        "query": {"type": "string"}, "path": {"type": "string", "description": "Optional path prefix"},
    }, ["query"]),
    spec("dependency_graph", "Build an evidence-backed dependency and symbol relationship graph for the workspace. Filter by an optional query.", {
        "query": {"type": "string", "description": "Optional symbol, path, route, or keyword filter"},
        "path": {"type": "string", "description": "Optional path prefix"},
    }, []),
    spec("read_file", "Read an exact line range from a text file.", {
        "path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    }, ["path"]),
    spec("replace_in_file", "Propose a precise replacement in an existing text file. old_text must occur exactly once.", {
        "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
    }, ["path", "old_text", "new_text"]),
    spec("replace_line_range", "Propose a replacement for an exact line range in a large text file. Read the range first.", {
        "path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1}, "new_text": {"type": "string"},
    }, ["path", "start_line", "end_line", "new_text"]),
    spec("create_file", "Propose a new text file with the appropriate extension and complete content.", {
        "path": {"type": "string"}, "content": {"type": "string"},
    }, ["path", "content"]),
    spec("delete_file", "Propose deletion of an existing file only when required by the task.", {
        "path": {"type": "string"},
    }, ["path"]),
    spec("update_plan", "Publish or update the visible execution plan.", {
        "steps": {"type": "array", "items": {"type": "object", "properties": {
            "step": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
        }, "required": ["step", "status"]}},
    }, ["steps"]),
    spec("validate_overlay", "Validate proposed edits before presenting a diff.", {}, []),
    spec("propose_command", "Propose an approved, non-shell validation command. Execution requires user approval.", {
        "command": {"type": "array", "items": {"type": "string"}},
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300}
    }, ["command"]),
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
    plan: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)

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
            self.events.append({"tool": name, "input": data, "status": "error", "error": str(error), "feedback": "Retry with corrected arguments or inspect more context before falling back."})
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

    def tool_find_relationships(self, query: str, path: str = "") -> dict:
        result = self.tool_search_text(query, path)
        self.relationships = [{**match, "relation": "text-reference"} for match in result["matches"]]
        return {"query": query, "evidence": self.relationships, "truncated": result["truncated"]}

    def tool_dependency_graph(self, query: str = "", path: str = "") -> dict:
        graph = build_index(self.root, self.config.workspace_max_files)
        if path:
            graph["nodes"] = [n for n in graph["nodes"] if n.get("path", "").startswith(path)]
            graph["edges"] = [e for e in graph["edges"] if e.get("from", "").startswith(path)]
            graph["evidence"] = [e for e in graph["evidence"] if e.get("source", "").startswith(path)]
        if query:
            q = query.lower()
            graph["nodes"] = [n for n in graph["nodes"] if q in str(n).lower()]
            graph["edges"] = [e for e in graph["edges"] if q in str(e).lower()]
            graph["evidence"] = [e for e in graph["evidence"] if q in str(e).lower()]
        self.relationships = graph["evidence"]
        return {"query": query, "graph": graph, "summary": f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {len(graph['evidence'])} evidence records"}

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

    def tool_replace_line_range(self, path: str, start_line: int, end_line: int, new_text: str) -> dict:
        if end_line < start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        content = self._content(path)
        lines = content.splitlines(keepends=True)
        if start_line > len(lines) or end_line > len(lines):
            raise ValueError(f"Line range {start_line}-{end_line} is outside {path} ({len(lines)} lines)")
        self._remember(path)
        replacement = new_text if not new_text or new_text.endswith("\n") else new_text + "\n"
        self.overlays[path] = "".join(lines[:start_line - 1] + [replacement] + lines[end_line:])
        return {"proposed": path, "operation": "update", "range": [start_line, end_line]}

    def tool_delete_file(self, path: str) -> dict:
        self._content(path)
        self._remember(path)
        self.overlays[path] = None
        return {"proposed": path, "operation": "delete"}

    def tool_update_plan(self, steps: list[dict]) -> dict:
        allowed = {"pending", "in_progress", "completed"}
        if len(steps) > 20 or any(not item.get("step") or item.get("status") not in allowed for item in steps):
            raise ValueError("Plan must have at most 20 valid steps")
        self.plan = steps
        return {"planUpdated": True, "stepCount": len(steps)}

    def tool_validate_overlay(self) -> dict:
        errors = self.validate_proposals()
        result = {"valid": not errors, "errors": errors, "files": list(self.overlays)}
        if errors:
            self.events.append({"tool": "critic", "status": "error", "feedback": "Repair proposed files before presenting the diff.", "errors": errors})
        else:
            self.events.append({"tool": "critic", "status": "success", "feedback": "Overlay passed structural validation."})
        return result

    def tool_propose_command(self, command: list[str], timeout_seconds: int = 60) -> dict:
        validate_command(command)
        proposal = {"command": command, "timeout_seconds": min(timeout_seconds, 300), "root": str(self.root)}
        self.events.append({"tool": "command", "status": "awaiting_user_approval", "command": command})
        return {"commandProposal": proposal, "status": "awaiting_user_approval"}

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

    def validate_proposals(self) -> list[str]:
        errors = []
        for path, content in self.overlays.items():
            if content is not None and not content.strip():
                errors.append(f"{path}: proposed content is empty")
            if content is not None and "\x00" in content:
                errors.append(f"{path}: proposed content contains binary data")
        return errors


ALLOWED_COMMANDS = {"python", "python3", "pytest", "ruff", "mypy", "npm", "pnpm", "npx", "tsc"}


def validate_command(command: list[str]) -> None:
    if not command or command[0].split("/")[-1] not in ALLOWED_COMMANDS:
        raise ValueError("Command is not allowlisted")
    if any(part in {";", "&&", "||", "|", ">", "<", "`"} for part in command):
        raise ValueError("Shell operators are not allowed")


def run_safe_command(root: Path, command: list[str], timeout_seconds: int = 60) -> dict:
    validate_command(command)
    try:
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                   timeout=min(timeout_seconds, 300), shell=False)
        return {"command": command, "returnCode": completed.returncode,
                "stdout": completed.stdout[-20_000:], "stderr": completed.stderr[-20_000:],
                "timedOut": False}
    except subprocess.TimeoutExpired as error:
        return {"command": command, "returnCode": None, "stdout": (error.stdout or "")[-20_000:],
                "stderr": (error.stderr or "")[-20_000:], "timedOut": True}
