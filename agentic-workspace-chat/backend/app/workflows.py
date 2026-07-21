from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Workflow:
    name: str
    max_steps: int
    plan: list[dict]
    requires_checkpoint: bool = False


def workflow_guidance(workflow: Workflow, approved: bool = False) -> str:
    common = (
        f"Active workflow: {workflow.name}. Use no more than {workflow.max_steps} agent rounds. "
        "Stop when the plan criteria have evidence; do not exhaustively inspect unrelated files. "
    )
    if workflow.name == "diagnosis":
        return common + "Parse the failure, trace callers/imports/contracts/tests, identify root cause, and include only evidence-backed dependent changes plus regression validation."
    if workflow.name == "cross_layer_change":
        return common + (
            "Treat the backend response as a versioned contract. Inspect its producer and all frontend consumers, then update API types, service mapping, UI state, accessibility, and tests together. "
            "Explicitly distinguish loading, empty, intentionally skipped, failed, and successful results. For skipped generation preserve and display structured reason and confidence when the contract provides them. "
            "Use dependency_graph or impact_analysis before editing and explain why every proposed file is affected."
        )
    if workflow.name == "architecture_comparison":
        return common + "Locate both entry points, compare orchestration, prompts, models, data flow, consumers, persistence, and validation; answer when these dimensions are covered."
    if workflow.name == "architecture_migration":
        checkpoint = "The user approved the plan; proceed phase by phase." if approved else "This is the design checkpoint: analyze and publish the phased migration plan, but do not propose edits until the user approves it."
        return common + "Map source and target patterns, preserve domain-specific behavior, trace all consumers, tests, configuration and docs. " + checkpoint
    return common


def _plan(*steps: str) -> list[dict]:
    return [{"step": step, "status": "in_progress" if index == 0 else "pending"} for index, step in enumerate(steps)]


def classify_request(message: str) -> Workflow:
    text = message.lower()
    if re.search(r"\b(?:hello|hi|hey)\b", text) and len(text) < 80:
        return Workflow("simple", 2, _plan("Respond to the request"))
    if any(word in text for word in ("error", "exception", "traceback", "failed", "stack trace")):
        return Workflow("diagnosis", 10, _plan(
            "Parse the reported failure", "Locate the failing symbol", "Trace dependent files",
            "Identify the root cause", "Prepare and validate a coordinated fix",
        ))
    cross_layer = (
        any(word in text for word in ("backend", "api", "response", "contract"))
        and any(word in text for word in ("frontend", "ui", "dialog", "card"))
        and any(word in text for word in ("change", "update", "implement", "add", "show"))
    )
    if cross_layer:
        return Workflow("cross_layer_change", 12, _plan(
            "Inspect the backend response contract and behavior", "Trace frontend consumers and dependent types",
            "Define loading, empty, skipped, error, and success states", "Prepare coordinated backend and frontend changes",
            "Add contract and UI regression tests", "Validate the complete flow",
        ))
    if any(word in text for word in ("architecture", "compare", "different from")):
        migration = any(word in text for word in ("replace", "migrate", "follow", "similar to", "refactor"))
        if migration:
            return Workflow("architecture_migration", 16, _plan(
                "Map the source architecture", "Map the target architecture", "Define compatibility boundaries",
                "Prepare phased changes", "Update dependent consumers", "Validate behavior",
            ), requires_checkpoint=True)
        return Workflow("architecture_comparison", 8, _plan(
            "Locate both architecture entry points", "Compare orchestration and data flow",
            "Trace dependent consumers", "Summarize differences and recommendations",
        ))
    if any(word in text for word in ("fix", "implement", "change", "add ", "update", "refactor")):
        return Workflow("code_change", 12, _plan(
            "Understand the requested change", "Inspect affected and dependent files",
            "Prepare reviewed changes", "Validate the result",
        ))
    return Workflow("repository_analysis", 6, _plan(
        "Understand the question", "Gather targeted repository evidence", "Answer with evidence",
    ))
