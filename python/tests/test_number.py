import io
import json

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.number import NumberPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_integer(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": 42}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Enter a number")
    result = p.execute()

    assert result == 42
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "number"


def test_agent_mode_float(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": 3.14}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Pi?")
    assert p.execute() == 3.14


def test_agent_mode_string_number(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "99"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Num?")
    assert p.execute() == 99


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Num?", default=10)
    assert p.execute() == 10


def test_agent_mode_min_violation(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": 3}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Num?", min=5)
    with pytest.raises(ValidationError, match="at least 5"):
        p.execute()


def test_agent_mode_max_violation(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": 100}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Num?", max=50)
    with pytest.raises(ValidationError, match="at most 50"):
        p.execute()


def test_agent_mode_float_not_allowed(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": 3.5}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Int only?", float_allowed=False)
    with pytest.raises(ValidationError, match="Decimal numbers are not allowed"):
        p.execute()


def test_agent_mode_float_whole_number_ok(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": 5.0}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Int only?", float_allowed=False)
    result = p.execute()
    assert result == 5
    assert isinstance(result, int)


def test_agent_mode_invalid_string(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    # Provide 3 bad answers to exhaust retries
    lines = "".join(json.dumps({"answer": "abc"}) + "\n" for _ in range(3))
    stdin = io.StringIO(lines)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = NumberPrompt("Num?")
    with pytest.raises(ValidationError, match="Not a valid number"):
        p.execute()


def test_agent_dict_includes_options():
    p = NumberPrompt("Num?", min=0, max=100, float_allowed=False)
    d = p._to_agent_dict()
    assert d["min"] == 0
    assert d["max"] == 100
    assert d["float_allowed"] is False


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.number.pt_prompt", lambda _: "42")
    p = NumberPrompt("Num?")
    assert p.execute() == 42


def test_terminal_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.number.pt_prompt", lambda _: "")
    p = NumberPrompt("Num?", default=7)
    assert p.execute() == 7
