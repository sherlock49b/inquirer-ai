import io
import json

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.rawlist import RawlistPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_by_index(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": 2}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = RawlistPrompt("Pick", choices=["Alpha", "Beta", "Gamma"])
    result = p.execute()

    assert result == "Beta"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "rawlist"
    assert len(prompt_data["choices"]) == 3


def test_agent_mode_by_value(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Alpha"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = RawlistPrompt("Pick", choices=["Alpha", "Beta"])
    assert p.execute() == "Alpha"


def test_agent_mode_invalid(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": 99}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = RawlistPrompt("Pick", choices=["Alpha", "Beta"])
    with pytest.raises(ValidationError):
        p.execute()


def test_empty_choices_raises():
    with pytest.raises(ValueError, match="choices cannot be empty"):
        RawlistPrompt("Pick", choices=[])


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.rawlist.pt_prompt", lambda _: "1")
    p = RawlistPrompt("Pick", choices=["Alpha", "Beta"])
    assert p.execute() == "Alpha"
