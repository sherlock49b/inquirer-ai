import io
import json
from unittest.mock import patch

import pytest

from inquirer_ai.exceptions import InvalidChoiceError, PromptAbortedError, ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": ["Auth", "DB"]}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt("Select features", choices=["Auth", "DB", "Cache"])
    result = p.execute()
    assert result == ["Auth", "DB"]

    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "checkbox"
    assert len(prompt_data["choices"]) == 3


def test_agent_mode_empty_selection(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": []}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt("Select features", choices=["Auth", "DB"])
    result = p.execute()
    assert result == []


def test_agent_mode_invalid_choice(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": ["InvalidFeature"]}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt("Select features", choices=["Auth", "DB"])
    with pytest.raises(ValidationError):
        p.execute()


def test_agent_mode_not_a_list(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Auth"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt("Select features", choices=["Auth", "DB"])
    with pytest.raises(ValidationError):
        p.execute()


def test_empty_choices_raises():
    with pytest.raises(InvalidChoiceError, match="choices cannot be empty"):
        CheckboxPrompt("Select features", choices=[])


def test_agent_mode_validate_minimum_selection(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": ["Auth"]}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt(
        "Select features",
        choices=["Auth", "DB", "Cache"],
        validate=lambda v: True if len(v) >= 2 else "Select at least 2",
    )
    with pytest.raises(ValidationError, match="Select at least 2"):
        p.execute()


def test_agent_mode_with_dict_choices(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": ["auth"]}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt(
        "Select features",
        choices=[
            {"name": "Authentication", "value": "auth"},
            {"name": "Database", "value": "db"},
        ],
    )
    result = p.execute()
    assert result == ["auth"]


def test_terminal_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.choice_base.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = ["Auth", "DB"]
        p = CheckboxPrompt("Select features", choices=["Auth", "DB", "Cache"])
        assert p.execute() == ["Auth", "DB"]


def test_terminal_mode_empty_selection(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.choice_base.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = []
        p = CheckboxPrompt("Select features", choices=["Auth", "DB"])
        assert p.execute() == []


def test_terminal_mode_abort(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.choice_base.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = None
        p = CheckboxPrompt("Select features", choices=["Auth", "DB"])
        with pytest.raises(PromptAbortedError):
            p.execute()
