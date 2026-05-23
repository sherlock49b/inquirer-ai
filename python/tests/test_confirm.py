import io
import json
from unittest.mock import call

from inquirer_ai.prompts.confirm import ConfirmPrompt


def test_agent_mode_true(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": True}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = ConfirmPrompt("Proceed?")
    result = p.execute()

    assert result is True
    prompt_data = json.loads(stdout.getvalue().strip())
    assert prompt_data["type"] == "confirm"


def test_agent_mode_false(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": False}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = ConfirmPrompt("Proceed?").execute()
    assert result is False


def test_agent_mode_string_yes(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "yes"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = ConfirmPrompt("Proceed?").execute()
    assert result is True


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    p = ConfirmPrompt("Proceed?", default=True)
    prompt_data_expected = p._to_agent_dict()
    assert prompt_data_expected["default"] is True


def test_terminal_mode_yes(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.confirm.pt_prompt", lambda _: "y")
    assert ConfirmPrompt("Proceed?").execute() is True


def test_terminal_mode_no(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.confirm.pt_prompt", lambda _: "n")
    assert ConfirmPrompt("Proceed?").execute() is False


def test_terminal_mode_empty_uses_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.confirm.pt_prompt", lambda _: "")
    assert ConfirmPrompt("Proceed?", default=True).execute() is True
    assert ConfirmPrompt("Proceed?", default=False).execute() is False


def test_terminal_mode_invalid_then_valid(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    responses = iter(["maybe", "y"])
    monkeypatch.setattr("inquirer_ai.prompts.confirm.pt_prompt", lambda _: next(responses))
    assert ConfirmPrompt("Proceed?").execute() is True
