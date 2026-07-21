"""Verifies the profile can currently obtain credentials via STS."""

from __future__ import annotations

from app.llm.aws_session_manager import AwsSessionManager


class CredentialMonitor:
    def __init__(self, session_manager: AwsSessionManager) -> None:
        self.session_manager = session_manager

    def verify(self) -> dict:
        session = self.session_manager.create_session()
        sts = session.client("sts")
        return sts.get_caller_identity()
