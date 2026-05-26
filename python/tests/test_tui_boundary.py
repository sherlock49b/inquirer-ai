"""TUI boundary tests for Select and Checkbox prompts in agent mode.

Covers edge cases around choice lists: single choice, large lists, disabled,
separators, required checkbox, select-all, duplicates, unicode, empty/long names.
"""

from __future__ import annotations

import io
import json

import pytest

from inquirer_ai.choice import Separator
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.select import SelectPrompt
from tests.conftest import parse_prompt_from_stdout


def _setup_agent(monkeypatch, answer, stdout=None):
    """Helper: configure agent-mode stdin/stdout with a single JSON answer."""
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": answer}) + "\n")
    if stdout is None:
        stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)
    return stdout


def _setup_agent_multi(monkeypatch, answers, stdout=None):
    """Helper: configure agent-mode stdin/stdout with multiple JSON answers (for retries)."""
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    lines = "".join(json.dumps({"answer": a}) + "\n" for a in answers)
    stdin = io.StringIO(lines)
    if stdout is None:
        stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)
    return stdout


# ---------- 1. Single choice select ----------


def test_select_single_choice(monkeypatch):
    """A select prompt with exactly one choice should work correctly."""
    stdout = _setup_agent(monkeypatch, "only")
    p = SelectPrompt("Pick one", choices=[{"name": "Only Option", "value": "only"}])
    result = p.execute()
    assert result == "only"

    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "select"
    assert len(prompt_data["choices"]) == 1


# ---------- 2. Large choice list (100+) ----------


def test_select_large_choice_list(monkeypatch):
    """Select with 100+ choices: serialization and answer matching."""
    choices = [{"name": f"Option {i}", "value": f"opt_{i}"} for i in range(150)]
    stdout = _setup_agent(monkeypatch, "opt_99")

    p = SelectPrompt("Pick", choices=choices)
    result = p.execute()
    assert result == "opt_99"

    prompt_data = parse_prompt_from_stdout(stdout)
    assert len(prompt_data["choices"]) == 150
    # Verify round-trip: every choice serialized
    values = [c["value"] for c in prompt_data["choices"]]
    assert "opt_0" in values
    assert "opt_149" in values


def test_checkbox_large_choice_list(monkeypatch):
    """Checkbox with 100+ choices: select several from a large list."""
    choices = [f"item_{i}" for i in range(120)]
    selected = ["item_0", "item_59", "item_119"]
    stdout = _setup_agent(monkeypatch, selected)

    p = CheckboxPrompt("Pick many", choices=choices)
    result = p.execute()
    assert result == selected

    prompt_data = parse_prompt_from_stdout(stdout)
    assert len(prompt_data["choices"]) == 120


# ---------- 3. Disabled choices filtered from agent dict ----------


def test_disabled_choices_in_agent_dict():
    """Disabled choices appear in agent dict with a disabled field."""
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": "Available", "value": "a"},
            {"name": "Unavailable", "value": "b", "disabled": "out of stock"},
        ],
    )
    d = p._to_agent_dict()
    choice_dicts = d["choices"]
    # Disabled choice should still be listed (with disabled flag) so the agent sees it
    assert len(choice_dicts) == 2
    disabled_items = [c for c in choice_dicts if c.get("disabled")]
    assert len(disabled_items) == 1
    assert disabled_items[0]["disabled"] == "out of stock"


def test_select_disabled_choice_rejected(monkeypatch):
    """Selecting a disabled choice in agent mode raises ValidationError."""
    _setup_agent_multi(monkeypatch, ["b", "b", "b"])
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": "Available", "value": "a"},
            {"name": "Unavailable", "value": "b", "disabled": True},
        ],
    )
    with pytest.raises(ValidationError):
        p.execute()


# ---------- 4. Separator not in selectable choices ----------


def test_separator_not_selectable():
    """Separators should not appear in selectable indices."""
    p = SelectPrompt(
        "Pick",
        choices=[
            "Option A",
            Separator("--- divider ---"),
            "Option B",
        ],
    )
    indices = p._selectable_indices()
    # Separator is at index 1; should not be selectable
    assert 1 not in indices
    assert len(indices) == 2


def test_separator_in_agent_dict():
    """Separators should appear in the agent dict with type=separator."""
    p = SelectPrompt(
        "Pick",
        choices=[
            "Option A",
            Separator("--- divider ---"),
            "Option B",
        ],
    )
    d = p._to_agent_dict()
    sep_items = [c for c in d["choices"] if c.get("type") == "separator"]
    assert len(sep_items) == 1
    assert sep_items[0]["text"] == "--- divider ---"


def test_select_with_separator_agent_mode(monkeypatch):
    """Select should skip separator and accept valid choice in agent mode."""
    _setup_agent(monkeypatch, "Option B")
    p = SelectPrompt(
        "Pick",
        choices=[
            "Option A",
            Separator(),
            "Option B",
        ],
    )
    result = p.execute()
    assert result == "Option B"


# ---------- 5. Checkbox required=True, empty answer -> validation error ----------


def test_checkbox_required_empty_answer(monkeypatch):
    """Checkbox with required=True should reject empty selection."""
    _setup_agent_multi(monkeypatch, [[], [], []])
    p = CheckboxPrompt("Pick", choices=["A", "B", "C"], required=True)
    with pytest.raises(ValidationError, match="At least one choice is required"):
        p.execute()


def test_checkbox_required_custom_message(monkeypatch):
    """Checkbox with required=str should use the custom error message."""
    _setup_agent_multi(monkeypatch, [[], [], []])
    p = CheckboxPrompt("Pick", choices=["A", "B"], required="You must pick something!")
    with pytest.raises(ValidationError, match="You must pick something!"):
        p.execute()


def test_checkbox_required_nonempty_passes(monkeypatch):
    """Checkbox with required=True should accept non-empty selection."""
    _setup_agent(monkeypatch, ["A"])
    p = CheckboxPrompt("Pick", choices=["A", "B", "C"], required=True)
    result = p.execute()
    assert result == ["A"]


# ---------- 6. Checkbox select all choices ----------


def test_checkbox_select_all(monkeypatch):
    """Checkbox should accept all choices selected."""
    all_values = ["auth", "db", "cache"]
    _setup_agent(monkeypatch, all_values)
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": "Auth", "value": "auth"},
            {"name": "Database", "value": "db"},
            {"name": "Cache", "value": "cache"},
        ],
    )
    result = p.execute()
    assert result == all_values


def test_checkbox_select_all_with_disabled(monkeypatch):
    """Select all non-disabled choices; disabled ones should be excluded from valid set."""
    _setup_agent(monkeypatch, ["auth", "cache"])
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": "Auth", "value": "auth"},
            {"name": "Database", "value": "db", "disabled": True},
            {"name": "Cache", "value": "cache"},
        ],
    )
    result = p.execute()
    assert result == ["auth", "cache"]


# ---------- 7. Duplicate choice values - first match returned ----------


def test_select_duplicate_values_first_match(monkeypatch):
    """When multiple choices share a value, _validate_answer returns that value."""
    _setup_agent(monkeypatch, "dupe")
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": "First", "value": "dupe"},
            {"name": "Second", "value": "dupe"},
        ],
    )
    result = p.execute()
    assert result == "dupe"


def test_select_duplicate_values_by_name(monkeypatch):
    """Answering by name when values are duplicated should match the first one."""
    _setup_agent(monkeypatch, "First")
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": "First", "value": "dupe"},
            {"name": "Second", "value": "dupe"},
        ],
    )
    result = p.execute()
    assert result == "dupe"


def test_checkbox_duplicate_values(monkeypatch):
    """Checkbox with duplicate values should accept them."""
    _setup_agent(monkeypatch, ["dupe"])
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": "First", "value": "dupe"},
            {"name": "Second", "value": "dupe"},
        ],
    )
    result = p.execute()
    assert result == ["dupe"]


# ---------- 8. Unicode choice names (emoji, CJK) ----------


def test_select_unicode_emoji(monkeypatch):
    """Select prompt handles emoji choice names."""
    stdout = _setup_agent(monkeypatch, "rocket")
    p = SelectPrompt(
        "Pick emoji",
        choices=[
            {"name": "\U0001f680 Rocket", "value": "rocket"},
            {"name": "❤️ Heart", "value": "heart"},
        ],
    )
    result = p.execute()
    assert result == "rocket"

    prompt_data = parse_prompt_from_stdout(stdout)
    names = [c["name"] for c in prompt_data["choices"]]
    assert "\U0001f680 Rocket" in names


def test_select_unicode_cjk(monkeypatch):
    """Select prompt handles CJK characters."""
    stdout = _setup_agent(monkeypatch, "db_pg")
    p = SelectPrompt(
        "Choose",
        choices=[
            {"name": "数据库 PostgreSQL", "value": "db_pg"},
            {"name": "缓存 Redis", "value": "cache_redis"},
        ],
    )
    result = p.execute()
    assert result == "db_pg"

    prompt_data = parse_prompt_from_stdout(stdout)
    names = [c["name"] for c in prompt_data["choices"]]
    assert "数据库 PostgreSQL" in names


def test_select_unicode_answer_by_name(monkeypatch):
    """Select should accept CJK name as the answer."""
    _setup_agent(monkeypatch, "数据库")
    p = SelectPrompt("Choose", choices=["数据库", "缓存"])
    result = p.execute()
    assert result == "数据库"


def test_checkbox_unicode_mixed(monkeypatch):
    """Checkbox with mixed unicode choices."""
    _setup_agent(monkeypatch, ["\U0001f680", "数据库"])
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": "Rocket", "value": "\U0001f680"},
            {"name": "DB", "value": "数据库"},
            {"name": "Cache", "value": "cache"},
        ],
    )
    result = p.execute()
    assert result == ["\U0001f680", "数据库"]


# ---------- 9. Choice with empty string name ----------


def test_select_empty_name(monkeypatch):
    """Select with an empty-string name should still be selectable by value."""
    stdout = _setup_agent(monkeypatch, "empty_val")
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": "", "value": "empty_val"},
            {"name": "Normal", "value": "normal"},
        ],
    )
    result = p.execute()
    assert result == "empty_val"

    prompt_data = parse_prompt_from_stdout(stdout)
    names = [c["name"] for c in prompt_data["choices"]]
    assert "" in names


def test_checkbox_empty_name(monkeypatch):
    """Checkbox with an empty-string name choice."""
    _setup_agent(monkeypatch, ["empty_val"])
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": "", "value": "empty_val"},
            {"name": "Normal", "value": "normal"},
        ],
    )
    result = p.execute()
    assert result == ["empty_val"]


# ---------- 10. Choice with very long name ----------


def test_select_long_name(monkeypatch):
    """Select with a very long choice name should serialize and match correctly."""
    long_name = "A" * 5000
    stdout = _setup_agent(monkeypatch, "long_val")
    p = SelectPrompt(
        "Pick",
        choices=[
            {"name": long_name, "value": "long_val"},
            {"name": "Short", "value": "short"},
        ],
    )
    result = p.execute()
    assert result == "long_val"

    prompt_data = parse_prompt_from_stdout(stdout)
    found = [c for c in prompt_data["choices"] if c["value"] == "long_val"]
    assert len(found) == 1
    assert found[0]["name"] == long_name


def test_select_long_name_match_by_name(monkeypatch):
    """Select should accept a very long name as the answer."""
    long_name = "B" * 5000
    _setup_agent(monkeypatch, long_name)
    p = SelectPrompt(
        "Pick",
        choices=[long_name, "Short"],
    )
    result = p.execute()
    assert result == long_name


def test_checkbox_long_name(monkeypatch):
    """Checkbox with a very long choice name."""
    long_name = "C" * 5000
    _setup_agent(monkeypatch, ["long_val"])
    p = CheckboxPrompt(
        "Pick",
        choices=[
            {"name": long_name, "value": "long_val"},
            {"name": "Short", "value": "short"},
        ],
    )
    result = p.execute()
    assert result == ["long_val"]
