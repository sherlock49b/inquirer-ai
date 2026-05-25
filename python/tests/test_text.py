import io
import json

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.text import TextPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "hello"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Enter name")
    result = p.execute()

    assert result == "hello"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "input"
    assert prompt_data["kind"] == "prompt"
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
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["default"] == "world"


def test_agent_mode_validate_pass(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "alice@example.com"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Email", validate=lambda v: True if "@" in v else "Must contain @")
    assert p.execute() == "alice@example.com"


def test_agent_mode_validate_fail(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": "not-an-email"}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Email", validate=lambda v: True if "@" in v else "Must contain @")
    with pytest.raises(ValidationError, match="Must contain @"):
        p.execute()

    # Check that validation_error messages were sent
    output_lines = stdout.getvalue().strip().split("\n")
    validation_errors = [json.loads(line) for line in output_lines if '"validation_error"' in line]
    assert len(validation_errors) >= 1


def test_agent_mode_validate_retry_then_succeed(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    lines = json.dumps({"answer": "bad"}) + "\n" + json.dumps({"answer": "good@email.com"}) + "\n"
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Email", validate=lambda v: True if "@" in v else "Must contain @")
    assert p.execute() == "good@email.com"


def test_agent_mode_filter(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "  Hello  "}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Name", filter=lambda v: v.strip().lower())
    assert p.execute() == "hello"


def test_terminal_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _, **kw: "alice")
    p = TextPrompt("Name")
    assert p.execute() == "alice"


def test_terminal_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _, **kw: "")
    p = TextPrompt("Name", default="bob")
    assert p.execute() == "bob"


def test_terminal_mode_empty_no_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _, **kw: "")
    p = TextPrompt("Name")
    assert p.execute() == ""
