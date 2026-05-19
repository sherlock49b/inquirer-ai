import io
import json

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": ["Auth", "DB"]}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = CheckboxPrompt("Select features", choices=["Auth", "DB", "Cache"])
    result = p.execute()
    assert result == ["Auth", "DB"]

    prompt_data = json.loads(stdout.getvalue().strip())
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
