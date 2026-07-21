from types import SimpleNamespace
from unittest.mock import Mock

from botocore.exceptions import ClientError

from app import aws_session


def config():
    return SimpleNamespace(
        aws_auth_mode="sso", aws_profile="test-profile", aws_region="us-east-1",
        aws_sso_auto_login=True, aws_sso_login_timeout_seconds=30,
    )


def expired():
    return ClientError({"Error": {"Code": "ExpiredToken", "Message": "expired"}}, "GetCallerIdentity")


def test_valid_sso_session_does_not_launch_login(monkeypatch):
    session = Mock()
    session.client.return_value.get_caller_identity.return_value = {"Account": "123"}
    monkeypatch.setattr(aws_session, "_profile_session", Mock(return_value=session))
    run = Mock()
    monkeypatch.setattr(aws_session.subprocess, "run", run)

    assert aws_session.authenticated_session(config()) is session
    run.assert_not_called()


def test_expired_sso_session_logs_in_and_recreates_session(monkeypatch):
    expired_session = Mock()
    expired_session.client.return_value.get_caller_identity.side_effect = expired()
    refreshed_session = Mock()
    refreshed_session.client.return_value.get_caller_identity.return_value = {"Account": "123"}
    monkeypatch.setattr(
        aws_session, "_profile_session",
        Mock(side_effect=[expired_session, expired_session, refreshed_session]),
    )
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(aws_session.subprocess, "run", run)

    assert aws_session.authenticated_session(config()) is refreshed_session
    run.assert_called_once_with(
        ["aws", "sso", "login", "--profile", "test-profile"], check=False, timeout=30,
    )
