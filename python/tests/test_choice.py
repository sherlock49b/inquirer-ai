import io
import json

import pytest

from inquirer_ai.choice import Choice, Separator
from inquirer_ai.exceptions import InvalidChoiceError, ValidationError
from inquirer_ai.prompts.select import SelectPrompt
from tests.conftest import parse_prompt_from_stdout


def test_from_string():
    c = Choice.from_raw("hello")
    assert c.name == "hello"
    assert c.value == "hello"


def test_from_dict_with_name_and_value():
    c = Choice.from_raw({"name": "PostgreSQL", "value": "pg"})
    assert c.name == "PostgreSQL"
    assert c.value == "pg"


def test_from_dict_name_only():
    c = Choice.from_raw({"name": "MySQL"})
    assert c.name == "MySQL"
    assert c.value == "MySQL"


def test_from_choice_instance():
    original = Choice(name="test", value=42)
    c = Choice.from_raw(original)
    assert c is original


def test_from_invalid_type():
    with pytest.raises(InvalidChoiceError):
        Choice.from_raw(123)  # type: ignore[arg-type]


def test_to_dict():
    c = Choice(name="PostgreSQL", value="pg")
    assert c.to_dict() == {"name": "PostgreSQL", "value": "pg"}


def test_disabled_choice_from_dict():
    c = Choice.from_raw({"name": "Option", "value": "opt", "disabled": "coming soon"})
    assert c.disabled == "coming soon"


def test_disabled_choice_to_dict():
    c = Choice(name="X", value="x", disabled=True)
    d = c.to_dict()
    assert d["disabled"] is True


def test_short_and_description():
    c = Choice.from_raw({"name": "PostgreSQL", "value": "pg", "short": "PG", "description": "Relational DB"})
    assert c.short == "PG"
    assert c.description == "Relational DB"
    d = c.to_dict()
    assert d["short"] == "PG"
    assert d["description"] == "Relational DB"


def test_separator_to_dict():
    s = Separator("--- Section ---")
    assert s.to_dict() == {"type": "separator", "text": "--- Section ---"}


def test_separator_default_text():
    s = Separator()
    assert s.text == "────────"


def test_empty_dict_raises():
    with pytest.raises(InvalidChoiceError, match="must have at least"):
        Choice.from_raw({})


def test_select_with_separator(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "b"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt("Pick", choices=["a", Separator(), "b"])
    assert p.execute() == "b"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["choices"][1] == {"type": "separator", "text": "────────"}


def test_select_with_disabled_choice(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "b"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt("Pick", choices=["a", Choice("disabled_opt", "d", disabled="not available"), "b"])
    assert p.execute() == "b"


def test_select_disabled_choice_rejected(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "d"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SelectPrompt("Pick", choices=["a", Choice("Disabled", "d", disabled=True), "b"])
    with pytest.raises(ValidationError):
        p.execute()


def test_all_disabled_raises():
    with pytest.raises(InvalidChoiceError, match="at least one selectable"):
        SelectPrompt("Pick", choices=[Choice("X", "x", disabled=True)])
