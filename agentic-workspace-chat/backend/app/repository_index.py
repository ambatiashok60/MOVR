"""Dependency-free, evidence-first repository index.

The index intentionally uses conservative regexes (no language server required), but
keeps enough metadata for the agent to explain every relationship with a path/line.
"""
import re
from pathlib import Path
from .workspace import files

SYMBOL_RE = re.compile(
    r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)|"
    r"^\s*(?:export\s+)?(?:default\s+)?(?:class|interface|type|enum|function|const|let|var)\s+([A-Za-z_$][\w$]*)"
)
IMPORT_RE = re.compile(
    r"(?:from\s+([\w./@-]+)\s+import|from\s+['\"]([^'\"]+)['\"]|"
    r"import\s+(?:[^'\"]+?\s+from\s+)?['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))"
)
ROUTE_RE = re.compile(r"(?:@(app|router)\.(get|post|put|patch|delete)\s*\(|\.(get|post|put|patch|delete)\s*\()\s*['\"]([^'\"]+)")
CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


def _evidence(path: str, line: int, text: str, relation: str, confidence: str = "high") -> dict:
    return {"source": path, "line": line, "text": text[:500], "relation": relation, "confidence": confidence}


def build_index(root: Path, limit: int = 2000) -> dict:
    nodes, edges, evidence = [], [], []
    sources = files(root, limit)
    source_set = set(sources)
    symbols: dict[str, list[dict]] = {}
    for path in sources:
        try:
            lines = (root / path).read_text().splitlines()
        except (OSError, UnicodeError):
            continue
        for number, line in enumerate(lines, 1):
            match = SYMBOL_RE.search(line)
            if match:
                label = next(group for group in match.groups() if group)
                kind = "python-symbol" if path.endswith(".py") else "typescript-symbol"
                node = {"id": f"{path}::{label}", "kind": kind, "label": label, "path": path, "line": number}
                nodes.append(node)
                symbols.setdefault(label, []).append(node)
                evidence.append(_evidence(path, number, line, "defines"))
            for match in IMPORT_RE.finditer(line):
                target = next((group for group in match.groups() if group), "")
                edge = {"from": path, "to": target, "kind": "import", "confidence": "high",
                        "evidence": _evidence(path, number, line, "imports")}
                edges.append(edge)
            for match in ROUTE_RE.finditer(line):
                route = match.group(4)
                verb = match.group(2) or match.group(3) or "request"
                evidence.append(_evidence(path, number, line, f"route:{verb.upper()} {route}"))
                # Keep the compact legacy relation for clients that only need the path.
                evidence.append(_evidence(path, number, line, f"route:{route}"))
            # Calls are useful hints for tracing, but deliberately lower confidence
            # because regex cannot distinguish a call from a declaration/keyword.
            for called in CALL_RE.findall(line):
                if called in symbols and called not in {"if", "for", "while", "switch"}:
                    evidence.append(_evidence(path, number, line, f"calls:{called}", "medium"))
    for edge in edges:
        target = edge["to"]
        if target.startswith("."):
            base = Path(edge["from"]).parent / target
            candidates = [str(base), f"{base}.py", f"{base}.ts", f"{base}.tsx", f"{base}.js", str(base / "index.ts")]
            edge["to"] = next((candidate for candidate in candidates if candidate in source_set), target)
            edge["confidence"] = "high" if edge["to"] != target else "medium"
        elif target in source_set:
            edge["confidence"] = "high"
    # Attach symbol targets to imports where a local module exports a matching name.
    for edge in edges:
        target = edge["to"]
        for label, definitions in symbols.items():
            if label in str(edge["evidence"]["text"]):
                for definition in definitions:
                    if target == definition["path"] or target.endswith(Path(definition["path"]).stem):
                        edges.append({"from": edge["from"], "to": definition["id"], "kind": "symbol-import",
                                      "confidence": "medium", "evidence": edge["evidence"]})
                        break
    return {"nodes": nodes[:5000], "edges": edges[:10000], "evidence": evidence[:10000],
            "files": len(sources), "indexed": len(nodes), "confidence": "high" if nodes else "low"}
