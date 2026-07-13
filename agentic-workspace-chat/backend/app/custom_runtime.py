import ast
import json
import multiprocessing
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .config import Settings

SAFE_BUILTINS = {
    "bool": bool, "dict": dict, "enumerate": enumerate, "filter": filter,
    "float": float, "int": int, "len": len, "list": list, "map": map,
    "max": max, "min": min, "range": range, "reversed": reversed,
    "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
}
BLOCKED_NAMES = {"compile", "eval", "exec", "globals", "input", "locals", "open", "__import__"}
TOOL_NAME = re.compile(r"^[a-z][a-z0-9_-]{2,40}$")


def validate_code(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError("Imports and global/nonlocal declarations are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Dunder attribute access is not allowed")
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise ValueError(f"{node.id} is not allowed")
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    if functions != ["transform"]:
        raise ValueError("Code must define exactly one function: transform(files, args)")


def _execute_unbounded(code: str, source_files: dict[str, str], args: dict) -> dict[str, str | None]:
    namespace = {"__builtins__": SAFE_BUILTINS}
    exec(compile(code, "<agent-tool>", "exec"), namespace)
    result = namespace["transform"](dict(source_files), dict(args))
    if not isinstance(result, dict):
        raise ValueError("transform must return {path: content_or_none}")
    if len(result) > 100:
        raise ValueError("A tool may propose at most 100 file changes")
    for path, content in result.items():
        if not isinstance(path, str) or (content is not None and not isinstance(content, str)):
            raise ValueError("Tool output must map string paths to text or null")
    return result


def _worker(queue, code: str, source_files: dict[str, str], args: dict) -> None:
    try:
        queue.put((True, _execute_unbounded(code, source_files, args)))
    except Exception as error:
        queue.put((False, str(error)))


def execute_code(code: str, source_files: dict[str, str], args: dict,
                 timeout_seconds: int = 5) -> dict[str, str | None]:
    validate_code(code)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_worker, args=(queue, code, source_files, args))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError("Tool execution timed out")
    if queue.empty():
        raise ValueError("Tool execution failed without a result")
    success, result = queue.get()
    if not success:
        raise ValueError(result)
    return result


@dataclass
class ToolProposal:
    id: str
    name: str
    description: str
    code: str
    input_paths: list[str]
    args: dict
    persistent: bool = False


class CustomToolStore:
    def __init__(self, config: Settings):
        root = config.agent_state_dir.expanduser()
        self.root = root if root.is_absolute() else Path(__file__).resolve().parents[2] / root
        self.tools_dir = self.root / "tools"

    def proposal(self, name: str, description: str, code: str, input_paths: list[str],
                 args: dict, persistent: bool = False) -> ToolProposal:
        if not TOOL_NAME.fullmatch(name):
            raise ValueError("Tool names must use lowercase letters, numbers, hyphens, or underscores")
        validate_code(code)
        return ToolProposal(str(uuid4()), name, description, code, input_paths, args, persistent)

    def install(self, proposal: ToolProposal) -> None:
        target = self.tools_dir / proposal.name
        target.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": proposal.name, "description": proposal.description, "version": 1,
            "inputSchema": {"type": "object", "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                "args": {"type": "object"},
            }, "required": ["paths"]},
        }
        self._atomic(target / "tool.json", json.dumps(manifest, indent=2))
        self._atomic(target / "tool.py", proposal.code)

    def installed(self) -> list[dict]:
        result = []
        if not self.tools_dir.exists():
            return result
        for manifest in self.tools_dir.glob("*/tool.json"):
            try:
                data = json.loads(manifest.read_text())
                code = manifest.with_name("tool.py").read_text()
                validate_code(code)
                result.append({"manifest": data, "code": code})
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return result

    @staticmethod
    def _atomic(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content)
        temporary.replace(path)
