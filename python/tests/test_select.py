import io
import json
from unittest.mock import patch

import pytest

from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.prompts.select import SelectPrompt


def test_agent_mode_by_value(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "pg"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt(
        "Choose DB",
        choices=[
            {"name": "PostgreSQL", "value": "pg"},
            {"name": "MySQL", "value": "mysql"},
        ],
    )
    result = p.execute()
    assert result == "pg"

    prompt_data = json.loads(stdout.getvalue().strip())
    assert prompt_data["type"] == "select"
    assert len(prompt_data["choices"]) == 2


def test_agent_mode_by_name(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "PostgreSQL"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt("Choose DB", choices=["PostgreSQL", "MySQL"])
    result = p.execute()
    assert result == "PostgreSQL"


def test_agent_mode_invalid_choice(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Oracle"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt("Choose DB", choices=["PostgreSQL", "MySQL"])
    with pytest.raises(ValidationError):
        p.execute()


def test_empty_choices_raises():
    with pytest.raises(ValueError, match="choices cannot be empty"):
        SelectPrompt("Choose DB", choices=[])


def test_agent_dict_includes_choices():
    p = SelectPrompt(
        "Choose DB",
        choices=["PostgreSQL", "MySQL"],
        default="MySQL",
    )
    d = p._to_agent_dict()
    assert d["choices"] == [
        {"name": "PostgreSQL", "value": "PostgreSQL"},
        {"name": "MySQL", "value": "MySQL"},
    ]
    assert d["default"] == "MySQL"


def test_terminal_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.select.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = "pg"
        p = SelectPrompt(
            "Choose DB",
            choices=[
                {"name": "PostgreSQL", "value": "pg"},
                {"name": "MySQL", "value": "mysql"},
            ],
        )
        assert p.execute() == "pg"


def test_terminal_mode_abort(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.select.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = None
        p = SelectPrompt("Choose DB", choices=["PostgreSQL", "MySQL"])
        with pytest.raises(PromptAbortedError):
            p.execute()
