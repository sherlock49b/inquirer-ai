import io
import json

from inquirer_ai.core import prompt
from inquirer_ai.prompts.text import TextPrompt


def test_transformer_changes_display_not_value(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _, **kw: "secret123")

    output_lines: list[str] = []
    monkeypatch.setattr("builtins.print", lambda s: output_lines.append(s))

    p = TextPrompt("Password?", transformer=lambda v: "*" * len(v))
    result = p.execute()

    assert result == "secret123"
    assert any("*********" in line for line in output_lines)
    assert not any("secret123" in line for line in output_lines)


def test_transformer_not_applied_to_return_value(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "hello"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Name?", transformer=lambda v: v.upper())
    result = p.execute()
    assert result == "hello"


def test_when_skips_question(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": False}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    questions = [
        {"type": "confirm", "name": "want_details", "message": "Details?"},
        {
            "type": "input",
            "name": "details",
            "message": "Enter details",
            "when": lambda answers: answers.get("want_details", False),
        },
    ]
    answers = prompt(questions)

    assert answers == {"want_details": False}
    assert "details" not in answers


def test_when_includes_question(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": True}) + "\n" + json.dumps({"answer": "my details"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    questions = [
        {"type": "confirm", "name": "want_details", "message": "Details?"},
        {
            "type": "input",
            "name": "details",
            "message": "Enter details",
            "when": lambda answers: answers.get("want_details", False),
        },
    ]
    answers = prompt(questions)

    assert answers == {"want_details": True, "details": "my details"}
