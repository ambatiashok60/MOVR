"""Dependency-free, evidence-first repository index.

The index intentionally uses conservative regexes (no language server required), but
keeps enough metadata for the agent to explain every relationship with a path/line.
"""
import re
import json
import hashlib
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
API_PATH_RE = re.compile(r"['\"](/api/[^'\"?#]*)")
HTTP_METHOD_RE = re.compile(r"\b(get|post|put|patch|delete)\b", re.IGNORECASE)


def _evidence(path: str, line: int, text: str, relation: str, confidence: str = "high") -> dict:
    return {"source": path, "line": line, "text": text[:500], "relation": relation, "confidence": confidence}


def _parse_file(root: Path, path: str) -> dict:
    nodes, edges, evidence = [], [], []
    try:
        lines = (root / path).read_text().splitlines()
    except (OSError, UnicodeError):
        return {"nodes": [], "edges": [], "evidence": []}
    for number, line in enumerate(lines, 1):
        match = SYMBOL_RE.search(line)
        if match:
            label = next(group for group in match.groups() if group)
            kind = "python-symbol" if path.endswith(".py") else "typescript-symbol"
            nodes.append({"id": f"{path}::{label}", "kind": kind, "label": label, "path": path, "line": number})
            evidence.append(_evidence(path, number, line, "defines"))
        for match in IMPORT_RE.finditer(line):
            target = next((group for group in match.groups() if group), "")
            edges.append({"from": path, "to": target, "kind": "import", "confidence": "high",
                          "evidence": _evidence(path, number, line, "imports")})
        for match in ROUTE_RE.finditer(line):
            route = match.group(4)
            verb = match.group(2) or match.group(3) or "request"
            route_id = f"api:{verb.upper()}:{route}"
            nodes.append({"id": route_id, "kind": "api-route", "label": f"{verb.upper()} {route}", "path": path, "line": number})
            edges.append({"from": route_id, "to": path, "kind": "route-provider", "confidence": "high",
                          "evidence": _evidence(path, number, line, f"provides-api:{verb.upper()} {route}")})
            evidence.append(_evidence(path, number, line, f"route:{verb.upper()} {route}"))
            evidence.append(_evidence(path, number, line, f"route:{route}"))
        if "frontend" in Path(path).parts or Path(path).suffix in {".ts", ".tsx", ".js", ".jsx"}:
            for api_match in API_PATH_RE.finditer(line):
                route = api_match.group(1)
                method_match = HTTP_METHOD_RE.search(line)
                verb = method_match.group(1).upper() if method_match else "REQUEST"
                route_id = f"api:{verb}:{route}"
                nodes.append({"id": route_id, "kind": "api-consumer", "label": f"{verb} {route}", "path": path, "line": number})
                edges.append({"from": path, "to": route_id, "kind": "api-consumer", "confidence": "high",
                              "evidence": _evidence(path, number, line, f"consumes-api:{verb} {route}")})
                evidence.append(_evidence(path, number, line, f"api-consumer:{verb} {route}"))
    return {"nodes": nodes, "edges": edges, "evidence": evidence}


def _cache_path(root: Path, cache_dir: Path) -> Path:
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:20]
    return cache_dir / f"{key}.json"


def build_index(root: Path, limit: int = 2000, cache_dir: Path | None = None, force: bool = False) -> dict:
    """Build a per-file incremental index, reparsing only fresh or changed files."""
    sources = files(root, limit)
    source_set = set(sources)
    cache_dir = cache_dir or (Path(__file__).resolve().parents[2] / ".agent-state" / "indexes")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(root, cache_dir)
    cached = {"entries": {}}
    if path.exists() and not force:
        try:
            cached = json.loads(path.read_text())
            if cached.get("version") != 2:
                cached = {"entries": {}}
        except (OSError, json.JSONDecodeError):
            cached = {"entries": {}}
    entries, changed, reused = {}, 0, 0
    for relative in sources:
        target = root / relative
        stat = target.stat()
        signature = {"size": stat.st_size, "mtimeNs": stat.st_mtime_ns}
        old = cached.get("entries", {}).get(relative)
        if old and old.get("signature") == signature:
            entries[relative] = old
            reused += 1
            continue
        parsed = _parse_file(root, relative)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        entries[relative] = {"signature": signature, "sha256": digest, "index": parsed}
        changed += 1
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 2, "root": str(root), "entries": entries}))
    temporary.replace(path)
    nodes = [item for entry in entries.values() for item in entry["index"]["nodes"]]
    edges = [item for entry in entries.values() for item in entry["index"]["edges"]]
    evidence = [item for entry in entries.values() for item in entry["index"]["evidence"]]
    for edge in edges:
        target = edge["to"]
        if target.startswith("."):
            base = Path(edge["from"]).parent / target
            candidates = [str(base), f"{base}.py", f"{base}.ts", f"{base}.tsx", f"{base}.js", str(base / "index.ts")]
            edge["to"] = next((candidate for candidate in candidates if candidate in source_set), target)
            edge["confidence"] = "high" if edge["to"] != target else "medium"
        elif target in source_set:
            edge["confidence"] = "high"
    return {"nodes": nodes[:5000], "edges": edges[:10000], "evidence": evidence[:10000],
            "files": len(sources), "indexed": len(nodes), "changed": changed, "reused": reused,
            "deleted": len(set(cached.get("entries", {})) - source_set),
            "confidence": "high" if nodes else "low"}


def analyze_impact(graph: dict, query: str, limit: int = 30) -> dict:
    """Rank direct matches and their immediate dependency neighbors."""
    needle = query.lower().strip()
    scores: dict[str, int] = {}
    reasons: dict[str, set[str]] = {}

    def add(path: str, score: int, reason: str) -> None:
        if not path or path.startswith("api:"):
            return
        scores[path] = scores.get(path, 0) + score
        reasons.setdefault(path, set()).add(reason)

    matching_ids = set()
    for node in graph.get("nodes", []):
        if needle in str(node).lower():
            matching_ids.add(node.get("id", ""))
            add(node.get("path", ""), 4, f"matched {node.get('kind', 'node')}")
    for item in graph.get("evidence", []):
        if needle in str(item).lower():
            add(item.get("source", ""), 3, item.get("relation", "evidence"))
    for edge in graph.get("edges", []):
        rendered = str(edge).lower()
        direct = needle in rendered or edge.get("from") in matching_ids or edge.get("to") in matching_ids
        if direct:
            add(edge.get("from", ""), 2, edge.get("kind", "dependency"))
            add(edge.get("to", ""), 2, edge.get("kind", "dependency"))
    affected = [
        {"path": path, "score": score, "reasons": sorted(reasons.get(path, set()))}
        for path, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    return {"query": query, "affectedFiles": affected, "count": len(affected)}
