import io
import json

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
