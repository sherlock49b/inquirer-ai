import io
import json

import pytest

from inquirer_ai.exceptions import InvalidChoiceError, ValidationError
from inquirer_ai.prompts.expand import ExpandChoice, ExpandPrompt
from tests.conftest import parse_prompt_from_stdout

CHOICES = [
    {"key": "y", "name": "Overwrite", "value": "overwrite"},
    {"key": "n", "name": "Skip", "value": "skip"},
    {"key": "a", "name": "Abort", "value": "abort"},
]


def test_agent_mode_by_key(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "y"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = ExpandPrompt("Conflict?", choices=CHOICES)
    result = p.execute()

    assert result == "overwrite"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "expand"
    assert len(prompt_data["choices"]) == 3


def test_agent_mode_by_value(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "skip"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = ExpandPrompt("Conflict?", choices=CHOICES)
    assert p.execute() == "skip"


def test_agent_mode_invalid(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": "x"}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = ExpandPrompt("Conflict?", choices=CHOICES)
    with pytest.raises(ValidationError):
        p.execute()


def test_expand_choice_instance():
    choices = [ExpandChoice(key="y", name="Yes", value=True)]
    p = ExpandPrompt("Ok?", choices=choices)
    d = p._to_agent_dict()
    assert d["choices"][0] == {"key": "y", "name": "Yes", "value": True}


def test_empty_choices_raises():
    with pytest.raises(InvalidChoiceError, match="choices cannot be empty"):
        ExpandPrompt("Ok?", choices=[])


def test_duplicate_keys_raises():
    choices = [
        {"key": "y", "name": "Yes", "value": True},
        {"key": "y", "name": "Yep", "value": True},
    ]
    with pytest.raises(InvalidChoiceError, match="Duplicate"):
        ExpandPrompt("Ok?", choices=choices)


def test_missing_key_raises():
    with pytest.raises(InvalidChoiceError, match="must have a 'key'"):
        ExpandPrompt("Ok?", choices=[{"name": "Yes"}])


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.expand.pt_prompt", lambda _: "n")
    p = ExpandPrompt("Conflict?", choices=CHOICES)
    assert p.execute() == "skip"
