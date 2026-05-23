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


def test_unsafe_ask(monkeypatch):
    _agent(monkeypatch, "hello")
    result = questionary.text("Q").unsafe_ask()
    assert result == "hello"


def test_choice_with_description(monkeypatch):
    _agent(monkeypatch, "pg")
    c = questionary.Choice(title="PostgreSQL", value="pg", description="Relational DB")
    assert c.description == "Relational DB"
    result = questionary.select("DB?", choices=[c]).unsafe_ask()
    assert result == "pg"


def test_confirm_auto_enter_ignored(monkeypatch):
    _agent(monkeypatch, True)
    result = questionary.confirm("Ok?", auto_enter=True).unsafe_ask()
    assert result is True


# ── Extended compat tests: edge cases from code review ──


def test_choice_checked_multiple(monkeypatch):
    _agent(monkeypatch, ["a", "c"])
    choices = [
        questionary.Choice(title="A", value="a", checked=True),
        questionary.Choice(title="B", value="b"),
        questionary.Choice(title="C", value="c", checked=True),
    ]
    result = questionary.checkbox("Pick", choices=choices).ask()
    assert result == ["a", "c"]


def test_choice_disabled(monkeypatch):
    _agent(monkeypatch, "b")
    choices = [
        questionary.Choice(title="A", value="a", disabled="not available"),
        questionary.Choice(title="B", value="b"),
    ]
    result = questionary.select("Pick", choices=choices).ask()
    assert result == "b"


def test_choice_disabled_attr():
    c = questionary.Choice(title="X", value="x", disabled="reason")
    inquirer_choice = c.to_inquirer()
    assert inquirer_choice.disabled == "reason"


def test_choice_value_defaults_to_title():
    c = questionary.Choice(title="Hello")
    assert c.value == "Hello"


def test_choice_shortcut_key_accepted():
    c = questionary.Choice(title="X", value="x", shortcut_key="x")
    assert c.shortcut_key == "x"


def test_unsafe_ask_propagates_exception(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stdout", io.StringIO())

    import pytest

    from inquirer_ai.exceptions import PromptAbortedError

    with pytest.raises(PromptAbortedError):
        questionary.text("Q").unsafe_ask()


def test_ask_returns_none_on_keyboard_interrupt(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stdout", io.StringIO())

    # .ask() catches KeyboardInterrupt and returns None
    # PromptAbortedError is not KeyboardInterrupt, so it propagates
    # This tests that .ask() wraps the execution
    import pytest

    from inquirer_ai.exceptions import PromptAbortedError

    # For non-KeyboardInterrupt errors, ask() doesn't catch them
    with pytest.raises(PromptAbortedError):
        questionary.text("Q").ask()


def test_prompt_unknown_type_defaults_to_input(monkeypatch):
    _agent(monkeypatch, "hello")
    questions = [
        {"type": "unknown_type", "name": "x", "message": "Q"},
    ]
    answers = questionary.prompt(questions)
    assert answers == {"x": "hello"}


def test_prompt_checkbox_type(monkeypatch):
    _agent(monkeypatch, ["a"])
    questions = [
        {
            "type": "checkbox",
            "name": "features",
            "message": "Pick",
            "choices": [
                questionary.Choice(title="A", value="a", checked=True),
                questionary.Choice(title="B", value="b"),
            ],
        },
    ]
    answers = questionary.prompt(questions)
    assert answers == {"features": ["a"]}


def test_prompt_confirm_default_override(monkeypatch):
    _agent(monkeypatch, False)
    questions = [
        {"type": "confirm", "name": "ok", "message": "Sure?", "default": False},
    ]
    answers = questionary.prompt(questions)
    assert answers["ok"] is False


def test_select_with_default(monkeypatch):
    _agent(monkeypatch, "b")
    result = questionary.select("Pick", choices=["a", "b"], default="b").ask()
    assert result == "b"


def test_text_default_empty_string(monkeypatch):
    _agent(monkeypatch, "")
    result = questionary.text("Q", default="").ask()
    assert result == ""


def test_multiple_styles_ignored(monkeypatch):
    _agent(monkeypatch, "a", True, ["x"])
    questionary.select("Q", choices=["a"], style="s1").ask()
    questionary.confirm("Q", style="s2").ask()
    questionary.checkbox("Q", choices=["x"], style="s3").ask()
