import io
import json

from inquirer_ai.prompts.text import TextPrompt


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "hello"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Enter name")
    result = p.execute()

    assert result == "hello"
    prompt_data = json.loads(stdout.getvalue().strip())
    assert prompt_data["type"] == "input"
    assert prompt_data["message"] == "Enter name"


def test_agent_mode_with_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Enter name", default="world")
    result = p.execute()

    assert result == "world"
    prompt_data = json.loads(stdout.getvalue().strip())
    assert prompt_data["default"] == "world"
