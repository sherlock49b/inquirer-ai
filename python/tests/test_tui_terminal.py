"""TUI terminal-mode tests for inquirer-ai prompts.

These tests exercise the terminal rendering paths (NOT agent mode) by
simulating key sequences and mocking prompt_toolkit I/O.
"""

from __future__ import annotations

import pytest

from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt
from tests.helpers.tui import (
    DOWN,
    ENTER,
    SPACE,
    simulate_choice_prompt,
    simulate_input,
    strip_ansi,
)


@pytest.fixture(autouse=True)
def _force_human_mode(monkeypatch):
    """Ensure all tests in this module run in terminal (human) mode."""
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    # Remove socket env var if present
    monkeypatch.delenv("INQUIRER_AI_SOCKET", raising=False)


# =========================================================================
# 1. TextPrompt
# =========================================================================


class TestTextPrompt:
    def test_basic_input(self):
        """Typing 'hello' and pressing Enter returns 'hello'."""
        p = TextPrompt("Enter name")
        result = simulate_input(p, ["hello"])
        assert result == "hello"

    def test_default_on_empty(self):
        """Pressing Enter with no input returns the default value."""
        p = TextPrompt("Enter name", default="world")
        result = simulate_input(p, [""])
        assert result == "world"

    def test_non_empty_overrides_default(self):
        """Typing something overrides the default."""
        p = TextPrompt("Enter name", default="world")
        result = simulate_input(p, ["custom"])
        assert result == "custom"


# =========================================================================
# 2. ConfirmPrompt
# =========================================================================


class TestConfirmPrompt:
    def test_yes(self):
        """Typing 'y' returns True."""
        p = ConfirmPrompt("Continue?")
        result = simulate_input(p, ["y"])
        assert result is True

    def test_no(self):
        """Typing 'n' returns False."""
        p = ConfirmPrompt("Continue?")
        result = simulate_input(p, ["n"])
        assert result is False

    def test_empty_returns_default_false(self):
        """Pressing Enter with default=False returns False."""
        p = ConfirmPrompt("Continue?", default=False)
        result = simulate_input(p, [""])
        assert result is False

    def test_empty_returns_default_true(self):
        """Pressing Enter with default=True returns True."""
        p = ConfirmPrompt("Continue?", default=True)
        result = simulate_input(p, [""])
        assert result is True

    def test_yes_uppercase(self):
        """Typing 'Y' returns True."""
        p = ConfirmPrompt("Continue?")
        result = simulate_input(p, ["Y"])
        assert result is True

    def test_invalid_then_valid(self):
        """Invalid input is re-prompted; valid input succeeds."""
        p = ConfirmPrompt("Continue?")
        result = simulate_input(p, ["maybe", "y"])
        assert result is True


# =========================================================================
# 3. NumberPrompt
# =========================================================================


class TestNumberPrompt:
    def test_integer(self):
        """Typing '42' returns 42."""
        p = NumberPrompt("Enter number")
        result = simulate_input(p, ["42"])
        assert result == 42
        assert isinstance(result, int)

    def test_float(self):
        """Typing '3.14' returns 3.14."""
        p = NumberPrompt("Enter number")
        result = simulate_input(p, ["3.14"])
        assert result == 3.14

    def test_default_on_empty(self):
        """Pressing Enter with a default returns the default."""
        p = NumberPrompt("Enter number", default=10)
        result = simulate_input(p, [""])
        assert result == 10


# =========================================================================
# 4. SelectPrompt
# =========================================================================


class TestSelectPrompt:
    def test_first_choice(self):
        """Pressing Enter immediately selects the first choice."""
        p = SelectPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [ENTER])
        assert result == "alpha"

    def test_second_choice(self):
        """Down + Enter selects the second choice."""
        p = SelectPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [DOWN, ENTER])
        assert result == "beta"

    def test_third_choice(self):
        """Down + Down + Enter selects the third choice."""
        p = SelectPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [DOWN, DOWN, ENTER])
        assert result == "gamma"

    def test_with_values(self):
        """Choices with explicit values return the value, not the name."""
        p = SelectPrompt(
            "Pick DB",
            choices=[
                {"name": "PostgreSQL", "value": "pg"},
                {"name": "MySQL", "value": "mysql"},
                {"name": "SQLite", "value": "sqlite"},
            ],
        )
        result = simulate_choice_prompt(p, [DOWN, ENTER])
        assert result == "mysql"

    def test_default_cursor(self):
        """Default value positions the cursor on the matching choice."""
        p = SelectPrompt("Pick", choices=["alpha", "beta", "gamma"], default="gamma")
        result = simulate_choice_prompt(p, [ENTER])
        assert result == "gamma"


# =========================================================================
# 5. CheckboxPrompt
# =========================================================================


class TestCheckboxPrompt:
    def test_select_first_two(self):
        """Space + Down + Space + Enter selects the first two items."""
        p = CheckboxPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [SPACE, DOWN, SPACE, ENTER])
        assert result == ["alpha", "beta"]

    def test_select_none(self):
        """Pressing Enter immediately selects nothing."""
        p = CheckboxPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [ENTER])
        assert result == []

    def test_toggle_on_off(self):
        """Toggling the same item on and off deselects it."""
        p = CheckboxPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [SPACE, SPACE, ENTER])
        assert result == []

    def test_select_all_manually(self):
        """Select all three items one by one."""
        p = CheckboxPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, [SPACE, DOWN, SPACE, DOWN, SPACE, ENTER])
        assert result == ["alpha", "beta", "gamma"]

    def test_select_with_values(self):
        """Checkbox with explicit values returns values."""
        p = CheckboxPrompt(
            "Pick features",
            choices=[
                {"name": "Auth", "value": "auth"},
                {"name": "Database", "value": "db"},
                {"name": "Cache", "value": "cache"},
            ],
        )
        result = simulate_choice_prompt(p, [SPACE, DOWN, SPACE, ENTER])
        assert result == ["auth", "db"]

    def test_select_all_key(self):
        """Pressing 'a' toggles all items."""
        p = CheckboxPrompt("Pick", choices=["alpha", "beta", "gamma"])
        result = simulate_choice_prompt(p, ["a", ENTER])
        assert result == ["alpha", "beta", "gamma"]


# =========================================================================
# 6. strip_ansi utility
# =========================================================================


class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1b[38;2;159;164;227m? \x1b[0mHello"
        assert strip_ansi(text) == "? Hello"

    def test_plain_text_unchanged(self):
        assert strip_ansi("hello world") == "hello world"

    def test_removes_osc_sequences(self):
        text = "\x1b]0;title\x07content"
        assert strip_ansi(text) == "content"
