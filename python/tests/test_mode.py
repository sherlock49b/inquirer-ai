import os
from unittest import mock

from inquirer_ai.mode import is_agent_mode


def test_agent_mode_via_env():
    with mock.patch.dict(os.environ, {"INQUIRER_AI_MODE": "agent"}):
        assert is_agent_mode() is True


def test_human_mode_via_env():
    with mock.patch.dict(os.environ, {"INQUIRER_AI_MODE": "human"}):
        assert is_agent_mode() is False


def test_env_override_case_insensitive():
    with mock.patch.dict(os.environ, {"INQUIRER_AI_MODE": "AGENT"}):
        assert is_agent_mode() is True


def test_non_tty_defaults_to_agent(monkeypatch):
    monkeypatch.delenv("INQUIRER_AI_MODE", raising=False)
    with mock.patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = False
        assert is_agent_mode() is True


def test_tty_defaults_to_human(monkeypatch):
    monkeypatch.delenv("INQUIRER_AI_MODE", raising=False)
    with mock.patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        assert is_agent_mode() is False
