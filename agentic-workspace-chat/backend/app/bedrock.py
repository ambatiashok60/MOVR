from dataclasses import dataclass, field
import logging
from time import monotonic
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config as BotoConfig
from fastapi import HTTPException

from .agent_context import compacted_history, unfinished_plan
from .aws_session import authenticated_session
from .config import Settings
from .models import FileChange
from .tools import ToolRunner
from .workflows import Workflow, classify_request, workflow_guidance

logger = logging.getLogger("agentic-workspace-chat.bedrock")


@dataclass
class AgentResult:
    message: str
    changes: list[FileChange]
    events: list[dict]
    actions: list
    plan: list[dict]
    relationships: list[dict]
    usage: dict[str, int] = field(default_factory=lambda: {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0})




class Bedrock:
    def __init__(self, config: Settings):
        self.config = config

    def _client(self):
        session = authenticated_session(self.config)
        return session.client(
            "bedrock-runtime",
            config=BotoConfig(
                connect_timeout=self.config.bedrock_connect_timeout_seconds,
                read_timeout=self.config.bedrock_read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def run(self, root: Path, message: str, context: list[tuple[str, str]], detail: str = "auto", cancel_event: Event | None = None,
            history: list[dict] | None = None, prior_plan: list[dict] | None = None,
            progress=None, workflow: Workflow | None = None) -> AgentResult:
        workflow = workflow or classify_request(message)
        emit = progress or (lambda _event: None)
        file_context = "\n\n".join(f"<file path=\"{name}\">\n{text}\n</file>" for name, text in context)
        sections = []
        if file_context:
            sections.append(file_context)
        resumable = unfinished_plan(prior_plan)
        if resumable:
            plan_lines = "\n".join(f"- [{step.get('status')}] {step.get('step')}" for step in resumable)
            sections.append(
                "<active_plan>\nA plan from earlier in this session is still in progress. Resume it "
                f"unless the new request changes direction; update statuses as you work.\n{plan_lines}\n</active_plan>"
            )
        sections.append(f"<request>\n{message}\n</request>" if sections else message)
        prompt = "\n\n".join(sections)
        messages, context_info = compacted_history(
            history or [], self.config.agent_history_messages, self.config.agent_history_max_chars
        )
        context_info["repositoryContextTokens"] = len(file_context) // 4
        emit({"type": "context", **context_info})
        messages.append({"role": "user", "content": [{"text": prompt}]})
        runner = ToolRunner(root, self.config, progress=emit)
        runner.plan = list(resumable or workflow.plan)
        emit({"type": "classified", "workflow": workflow.name, "maxSteps": workflow.max_steps})
        emit({"type": "plan", "plan": runner.plan})
        final_text = ""
        usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        continuations = 0
        step = 0
        try:
            client = self._client()
            logger.info("Agent started model=%s workflow=%s max_steps=%s", self.config.bedrock_model_id, workflow.name, workflow.max_steps)
            while step < workflow.max_steps:
                step += 1
                if cancel_event and cancel_event.is_set():
                    return AgentResult(final_text + "\n\nGeneration stopped.", runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships, usage)
                round_started = monotonic()
                logger.info("Model round start round=%s planned=%s", step, bool(runner.plan))
                emit({"type": "activity", "activity": "model", "status": "started", "round": step})
                response = client.converse(
                    modelId=self.config.bedrock_model_id,
                    system=[{"text": (
                        "You are a migration-grade coding agent operating only inside the connected workspace. "
                        + workflow_guidance(workflow, "[plan approved]" in message.lower()) + " "
                        "First assess the request: for multi-step work (three or more distinct steps, migrations, new modules, "
                        "or anything spanning several files), publish a plan with update_plan BEFORE editing and keep each "
                        "step's status current as you work — publishing a plan extends your step budget. For simple questions "
                        "or single-file edits, skip the plan and act directly. "
                        "Explore with tools, read relevant ranges, and use precise edit tools when changes are requested. "
                        "For repository analysis or debugging, use find_relationships and cite its path, line, and matched text as evidence. "
                        "Use run_command to execute allowlisted validation commands (pytest, ruff, mypy, tsc) and iterate on their "
                        "output; remember commands see the on-disk state, not your unapplied proposals, so run them to diagnose "
                        "before editing or to verify previously applied changes. "
                        "When a tool returns an error or a target cannot be resolved, treat it as feedback: inspect again and retry within the step budget; do not silently downgrade. "
                        "Before presenting any edit, review it as a critic for completeness, consistency, and obvious structural errors, then repair it if needed. "
                        "Edits are proposals for user review. Never claim validation you did not run. "
                        + ("For questions requiring workspace context, explore the workspace and gather evidence before answering. For any question, give a detailed, structured answer with assumptions, evidence, examples, and next steps when useful. Use Markdown when useful." if detail == "detailed" else
                           "Be concise unless the task requires explanation." if detail == "brief" else
                           "Match answer depth to the task: concise for simple questions and detailed for migrations and analysis.")
                    )}],
                    messages=messages,
                    toolConfig=runner.tool_config(),
                    inferenceConfig={"maxTokens": self.config.bedrock_max_tokens, "temperature": 0.1},
                )
                round_usage = response.get("usage", {})
                usage["inputTokens"] += int(round_usage.get("inputTokens", 0))
                usage["outputTokens"] += int(round_usage.get("outputTokens", 0))
                usage["totalTokens"] += int(round_usage.get("totalTokens", 0))
                round_ms = round((monotonic() - round_started) * 1000)
                output = response["output"]["message"]
                messages.append(output)
                round_text = "".join(block.get("text", "") for block in output["content"])
                final_text += round_text
                for offset in range(0, len(round_text), 500):
                    emit({"type": "text", "text": round_text[offset:offset + 500]})
                uses = [block["toolUse"] for block in output["content"] if "toolUse" in block]
                runner.events.append({"tool": "model_round", "status": "success", "round": step, "elapsedMs": round_ms, "toolCalls": len(uses)})
                emit({"type": "usage", "usage": dict(usage), "round": step})
                emit({"type": "activity", "activity": "model", "status": "completed", "round": step, "elapsedMs": round_ms})
                logger.info(
                    "Model round complete round=%s elapsed_ms=%s tool_calls=%s input_tokens=%s output_tokens=%s stop_reason=%s",
                    step, round_ms, len(uses), round_usage.get("inputTokens", 0),
                    round_usage.get("outputTokens", 0), response.get("stopReason", "unknown"),
                )
                if not uses:
                    if response.get("stopReason") == "max_tokens" and continuations < self.config.agent_max_response_continuations:
                        continuations += 1
                        runner.events.append({"tool": "response_continuation", "status": "success", "part": continuations})
                        messages.append({"role": "user", "content": [{"text": (
                            "Continue the answer from exactly where you stopped. Do not repeat previous text. "
                            "Finish the requested analysis with concrete evidence and a complete conclusion."
                        )}]})
                        continue
                    errors = runner.validate_proposals()
                    if errors and continuations < self.config.agent_max_response_continuations:
                        continuations += 1
                        runner.events.append({"tool": "critic_repair", "status": "retry", "errors": errors})
                        messages.append({"role": "user", "content": [{"text": "Critic found proposal issues: " + "; ".join(errors) + ". Repair the proposal and re-check it before answering."}]})
                        continue
                    if runner.changes():
                        runner.events.append({"tool": "critic_repair", "status": "passed"})
                    return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships, usage)
                results = []
                read_only = {"list_files", "search_text", "read_file"}
                can_parallelize = len(uses) > 1 and all(use["name"] in read_only for use in uses)

                def execute_use(use):
                    if cancel_event and cancel_event.is_set():
                        return {"error": "Generation stopped"}
                    logger.info("Tool start round=%s tool=%s", step, use["name"])
                    return runner.execute(use["name"], use.get("input", {}))

                if can_parallelize:
                    logger.info("Parallel repository exploration tool_calls=%s", len(uses))
                    with ThreadPoolExecutor(max_workers=min(4, len(uses))) as executor:
                        values = list(executor.map(execute_use, uses))
                else:
                    values = [execute_use(use) for use in uses]
                for use, value in zip(uses, values):
                    results.append({"toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": value}],
                                                   "status": "error" if "error" in value else "success"}})
                messages.append({"role": "user", "content": results})
            final_text += "\n\nI reached the configured agent step limit. Review any proposed changes before continuing."
            return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships, usage)
        except (BotoCoreError, ClientError) as error:
            raise HTTPException(503, "Bedrock request failed after AWS session validation") from error
