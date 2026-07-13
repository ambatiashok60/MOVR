import boto3
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound
from fastapi import HTTPException

from .config import Settings
from .models import FileChange
from .tools import ToolRunner


@dataclass
class AgentResult:
    message: str
    changes: list[FileChange]
    events: list[dict]
    actions: list
    plan: list[dict]
    relationships: list[dict]


class Bedrock:
    def __init__(self, config: Settings):
        self.config = config

    def _client(self):
        try:
            if self.config.aws_auth_mode.lower() == "keys":
                if not self.config.aws_access_key_id or not self.config.aws_secret_access_key:
                    raise HTTPException(503, "AWS_AUTH_MODE=keys requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
                session = boto3.Session(
                    aws_access_key_id=self.config.aws_access_key_id,
                    aws_secret_access_key=self.config.aws_secret_access_key,
                    aws_session_token=self.config.aws_session_token,
                    region_name=self.config.aws_region,
                )
            else:
                session = boto3.Session(profile_name=self.config.aws_profile, region_name=self.config.aws_region)
            return session.client("bedrock-runtime")
        except ProfileNotFound as error:
            raise HTTPException(503, f"AWS profile '{self.config.aws_profile}' was not found") from error

    def run(self, root: Path, message: str, context: list[tuple[str, str]], detail: str = "auto", cancel_event: Event | None = None) -> AgentResult:
        file_context = "\n\n".join(f"<file path=\"{name}\">\n{text}\n</file>" for name, text in context)
        prompt = f"{file_context}\n\n<request>\n{message}\n</request>" if context else message
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        runner = ToolRunner(root, self.config)
        final_text = ""
        continuations = 0
        try:
            client = self._client()
            for _ in range(self.config.agent_max_steps):
                if cancel_event and cancel_event.is_set():
                    return AgentResult(final_text + "\n\nGeneration stopped.", runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships)
                response = client.converse(
                    modelId=self.config.bedrock_model_id,
                    system=[{"text": (
                        "You are a migration-grade coding agent operating only inside the connected workspace. "
                        "Explore with tools, read relevant ranges, and use precise edit tools when changes are requested. "
                        "For repository analysis or debugging, use find_relationships and cite its path, line, and matched text as evidence. "
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
                output = response["output"]["message"]
                messages.append(output)
                final_text += "".join(block.get("text", "") for block in output["content"])
                uses = [block["toolUse"] for block in output["content"] if "toolUse" in block]
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
                        return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships)
                results = []
                for use in uses:
                    if cancel_event and cancel_event.is_set():
                        return AgentResult(final_text + "\n\nGeneration stopped.", runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships)
                    value = runner.execute(use["name"], use.get("input", {}))
                    results.append({"toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": value}],
                                                   "status": "error" if "error" in value else "success"}})
                messages.append({"role": "user", "content": results})
            final_text += "\n\nI reached the configured agent step limit. Review any proposed changes before continuing."
            return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals, runner.plan, runner.relationships)
        except (BotoCoreError, ClientError) as error:
            raise HTTPException(503, "Bedrock failed. Run 'aws sso login --profile " + self.config.aws_profile + "' and retry") from error
