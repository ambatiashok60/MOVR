from pathlib import Path

from app.config import Settings


def test_allowed_roots_accept_comma_separated_env(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv("WORKSPACE_ALLOWED_ROOTS", "/tmp/one,/tmp/path with spaces")

    config = Settings(_env_file=None)

    assert config.workspace_allowed_roots == [Path("/tmp/one"), Path("/tmp/path with spaces")]


def test_allowed_roots_accept_json_array_env(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv(
        "WORKSPACE_ALLOWED_ROOTS",
        '["/tmp/one", "/tmp/path with spaces"]',
    )

    config = Settings(_env_file=None)

    assert config.workspace_allowed_roots == [Path("/tmp/one"), Path("/tmp/path with spaces")]


def test_allowed_roots_json_single_entry_keeps_no_brackets_or_quotes(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv(
        "WORKSPACE_ALLOWED_ROOTS",
        '["/Users/aambati/Documents/JIRA Tickets/comparison/Worktop_Trinet"]',
    )

    config = Settings(_env_file=None)

    assert config.workspace_allowed_roots == [
        Path("/Users/aambati/Documents/JIRA Tickets/comparison/Worktop_Trinet")
    ]
    rendered = str(config.workspace_allowed_roots[0])
    assert "[" not in rendered and '"' not in rendered


def test_allowed_roots_strip_quotes_and_whitespace(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv("WORKSPACE_ALLOWED_ROOTS", ' "/tmp/one" , \'/tmp/two\' ,, ')

    config = Settings(_env_file=None)

    assert config.workspace_allowed_roots == [Path("/tmp/one"), Path("/tmp/two")]


def test_allowed_roots_malformed_json_falls_back_to_comma_split(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    monkeypatch.setenv("WORKSPACE_ALLOWED_ROOTS", "[not-json,/tmp/two")

    config = Settings(_env_file=None)

    assert Path("/tmp/two") in config.workspace_allowed_roots
