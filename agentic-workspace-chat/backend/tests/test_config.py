from pathlib import Path

from app.config import Settings


def test_allowed_roots_accept_comma_separated_env(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv("WORKSPACE_ALLOWED_ROOTS", "/tmp/one,/tmp/path with spaces")

    config = Settings(_env_file=None)

    assert config.workspace_allowed_roots == [Path("/tmp/one"), Path("/tmp/path with spaces")]
