"""Small, dependency-free repository index used for explainable code navigation."""
import re
from pathlib import Path
from .workspace import files

DEF_RE = re.compile(r"\b(?:def|class|interface|type|function|const|let|var)\s+([A-Za-z_$][\w$]*)")
IMPORT_RE = re.compile(r"(?:from\s+([\w./-]+)\s+import|from\s+['\"]([^'\"]+)['\"]|import\s+(?:[^'\"]+?\s+from\s+)?['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))")
ROUTE_RE = re.compile(r"(?:@(app|router)\.(?:get|post|put|patch|delete)|\.(?:get|post|put|patch|delete)\s*\()\s*['\"]([^'\"]+)")

def build_index(root: Path, limit: int = 2000) -> dict:
    nodes, edges, evidence = [], [], []
    symbol_files: dict[str, str] = {}
    sources = files(root, limit)
    for path in sources:
        try: lines = (root / path).read_text().splitlines()
        except (OSError, UnicodeError): continue
        for n, line in enumerate(lines, 1):
            for symbol in DEF_RE.findall(line):
                nodes.append({"id": f"{path}::{symbol}", "kind": "symbol", "label": symbol, "path": path, "line": n})
                symbol_files.setdefault(symbol, path)
                evidence.append({"source": path, "line": n, "text": line[:500], "relation": "defines"})
            for match in IMPORT_RE.finditer(line):
                target = next((x for x in match.groups() if x), "")
                edges.append({"from": path, "to": target, "kind": "import", "evidence": {"path": path, "line": n, "text": line[:500]}})
            for _, route in ROUTE_RE.findall(line):
                evidence.append({"source": path, "line": n, "text": line[:500], "relation": f"route:{route}"})
    # Resolve imported local paths and symbol references to stable graph edges.
    for edge in edges:
        target = edge["to"]
        if target.startswith("."):
            base = Path(edge["from"]).parent / target
            candidates = [str(base), str(base)+".py", str(base)+".ts", str(base)+".js", str(base)/"index.ts"]
            resolved = next((p for p in candidates if p in sources), target)
            edge["to"] = resolved
    return {"nodes": nodes[:5000], "edges": edges[:5000], "evidence": evidence[:5000], "files": len(sources)}
