import io
import json

import pytest

from inquirer_ai.prompts.password import PasswordPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "s3cret"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = PasswordPrompt("Enter password")
    result = p.execute()

    assert result == "s3cret"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "password"
    assert prompt_data["mask"] == "*"


def test_agent_mode_no_mask(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "hidden"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = PasswordPrompt("Enter password", mask=None)
    result = p.execute()

    assert result == "hidden"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["mask"] is None


def test_format_answer_masked():
    p = PasswordPrompt("pw", mask="*")
    assert p._format_answer("hello") == "*****"


def test_format_answer_no_mask():
    p = PasswordPrompt("pw", mask=None)
    assert p._format_answer("hello") == "****"


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = PasswordPrompt("pw", default="default_pw")
    assert p.execute() == "default_pw"


def test_agent_mode_validate(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "ab"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    from inquirer_ai.exceptions import ValidationError

    p = PasswordPrompt("pw", validate=lambda v: len(v) >= 8 or "At least 8 characters")
    with pytest.raises(ValidationError, match="At least 8 characters"):
        p.execute()


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.password.pt_prompt", lambda *a, **kw: "mysecret")
    p = PasswordPrompt("pw")
    assert p.execute() == "mysecret"
