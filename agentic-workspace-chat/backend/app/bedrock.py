import boto3
from dataclasses import dataclass
from pathlib import Path
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


class Bedrock:
    def __init__(self, config: Settings):
        self.config = config

    def _client(self):
        try:
            session = boto3.Session(
                profile_name=self.config.aws_profile,
                region_name=self.config.aws_region,
            )
            return session.client("bedrock-runtime")
        except ProfileNotFound as error:
            raise HTTPException(503, f"AWS profile '{self.config.aws_profile}' was not found") from error

    def run(self, root: Path, message: str, context: list[tuple[str, str]]) -> AgentResult:
        file_context = "\n\n".join(f"<file path=\"{name}\">\n{text}\n</file>" for name, text in context)
        prompt = f"{file_context}\n\n<request>\n{message}\n</request>" if context else message
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        runner = ToolRunner(root, self.config)
        final_text = ""
        try:
            client = self._client()
            for _ in range(self.config.agent_max_steps):
                response = client.converse(
                    modelId=self.config.bedrock_model_id,
                    system=[{"text": (
                        "You are a migration-grade coding agent operating only inside the connected workspace. "
                        "Explore with tools, read relevant ranges, and use precise edit tools when changes are requested. "
                        "Edits are proposals for user review. Never claim validation you did not run."
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
                    return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals)
                results = []
                for use in uses:
                    value = runner.execute(use["name"], use.get("input", {}))
                    results.append({"toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": value}],
                                                   "status": "error" if "error" in value else "success"}})
                messages.append({"role": "user", "content": results})
            final_text += "\n\nI reached the configured agent step limit. Review any proposed changes before continuing."
            return AgentResult(final_text, runner.changes(), runner.events, runner.action_proposals)
        except (BotoCoreError, ClientError) as error:
            raise HTTPException(503, "Bedrock failed. Run 'aws sso login --profile " + self.config.aws_profile + "' and retry") from error
