"""Tests for the questionary compatibility layer."""

import io
import json

from inquirer_ai.compat import questionary


def _agent(monkeypatch, *answers):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    lines = "".join(json.dumps({"answer": a}) + "\n" for a in answers)
    monkeypatch.setattr("sys.stdin", io.StringIO(lines))
    monkeypatch.setattr("sys.stdout", io.StringIO())


def test_select_ask(monkeypatch):
    _agent(monkeypatch, "b")
    result = questionary.select("Pick", choices=["a", "b", "c"]).ask()
    assert result == "b"


def test_confirm_ask(monkeypatch):
    _agent(monkeypatch, True)
    result = questionary.confirm("Ok?").ask()
    assert result is True


def test_confirm_default_true(monkeypatch):
    _agent(monkeypatch, True)
    result = questionary.confirm("Ok?", default=True).ask()
    assert result is True


def test_text_ask(monkeypatch):
    _agent(monkeypatch, "hello")
    result = questionary.text("Name?").ask()
    assert result == "hello"


def test_text_with_filter(monkeypatch):
    _agent(monkeypatch, "  hello  ")
    result = questionary.text("Name?", filter=str.strip).ask()
    assert result == "hello"


def test_checkbox_ask(monkeypatch):
    _agent(monkeypatch, ["a", "c"])
    result = questionary.checkbox("Pick", choices=["a", "b", "c"]).ask()
    assert result == ["a", "c"]


def test_choice_title_value(monkeypatch):
    _agent(monkeypatch, "pg")
    c = questionary.Choice(title="PostgreSQL", value="pg")
    result = questionary.select("DB?", choices=[c, questionary.Choice(title="MySQL", value="mysql")]).ask()
    assert result == "pg"


def test_choice_checked_defaults(monkeypatch):
    _agent(monkeypatch, ["a"])
    choices = [
        questionary.Choice(title="A", value="a", checked=True),
        questionary.Choice(title="B", value="b"),
    ]
    result = questionary.checkbox("Pick", choices=choices).ask()
    assert result == ["a"]


def test_prompt_list_type(monkeypatch):
    _agent(monkeypatch, "b")
    questions = [
        {"type": "list", "name": "choice", "message": "Pick", "choices": ["a", "b"]},
    ]
    answers = questionary.prompt(questions)
    assert answers == {"choice": "b"}


def test_prompt_mixed_types(monkeypatch):
    _agent(monkeypatch, "Alice", True, "pg")
    questions = [
        {"type": "input", "name": "name", "message": "Name?"},
        {"type": "confirm", "name": "ok", "message": "Sure?"},
        {"type": "list", "name": "db", "message": "DB?", "choices": ["pg", "mysql"]},
    ]
    answers = questionary.prompt(questions)
    assert answers == {"name": "Alice", "ok": True, "db": "pg"}


def test_prompt_with_filter(monkeypatch):
    _agent(monkeypatch, "  hello  ")
    questions = [
        {"type": "input", "name": "msg", "message": "Msg?", "filter": str.strip},
    ]
    answers = questionary.prompt(questions)
    assert answers == {"msg": "hello"}


def test_style_ignored(monkeypatch):
    _agent(monkeypatch, "x")
    result = questionary.select("Q", choices=["x"], style="whatever").ask()
    assert result == "x"
