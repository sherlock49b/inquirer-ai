"""Property-based tests using hypothesis to find edge cases machines miss."""

import json
import string

from hypothesis import given, settings
from hypothesis import strategies as st

from inquirer_ai.choice import Choice, Separator, parse_choice
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.expand import ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.rawlist import RawlistPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

# ── Strategies ──

choice_name = st.text(min_size=1, max_size=50, alphabet=string.printable)
choice_value = st.one_of(st.text(min_size=1, max_size=20), st.integers(-1000, 1000), st.booleans())


# ── Choice roundtrip ──


@given(name=choice_name, value=choice_value)
@settings(max_examples=200)
def test_choice_to_dict_roundtrip(name, value):
    """Choice -> dict -> Choice should preserve name and value."""
    original = Choice(name=name, value=value)
    d = original.to_dict()
    restored = Choice.from_raw(d)
    assert restored.name == original.name
    assert restored.value == original.value


@given(name=choice_name)
@settings(max_examples=100)
def test_choice_from_string_roundtrip(name):
    """String choices should have name == value."""
    c = Choice.from_raw(name)
    assert c.name == name
    assert c.value == name


@given(
    items=st.lists(
        st.one_of(
            st.text(min_size=1, max_size=10),
            st.builds(Separator, text=st.text(min_size=1, max_size=10)),
        ),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_parse_choice_always_returns_choice_or_separator(items):
    """parse_choice should never raise on valid input types."""
    for item in items:
        result = parse_choice(item)
        assert isinstance(result, (Choice, Separator))


# ── Select: validate_answer invariant ──


@given(
    choices=st.lists(choice_name, min_size=1, max_size=10, unique=True),
    pick=st.integers(0, 9),
)
@settings(max_examples=200)
def test_select_validate_accepts_any_valid_choice(choices, pick):
    """SelectPrompt._validate_answer should accept any choice by name or value."""
    p = SelectPrompt("q", choices=choices)
    idx = pick % len(choices)
    result = p._validate_answer(choices[idx])
    assert result == choices[idx]


@given(
    choices=st.lists(choice_name, min_size=2, max_size=5, unique=True),
    bogus=st.text(min_size=1, max_size=10).filter(lambda t: t not in string.printable[:5]),
)
@settings(max_examples=100)
def test_select_validate_rejects_invalid(choices, bogus):
    """SelectPrompt._validate_answer should reject values not in choices."""
    if bogus in choices:
        return
    p = SelectPrompt("q", choices=choices)
    try:
        p._validate_answer(bogus)
    except ValidationError:
        return
    raise AssertionError(f"Should have rejected {bogus!r}")


# ── Number: boundary properties ──


@given(value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e15, max_value=1e15))
@settings(max_examples=200)
def test_number_validate_float(value):
    """NumberPrompt should accept any finite float when float_allowed=True."""
    p = NumberPrompt("q")
    result = p._validate_answer(value)
    assert result == value


@given(value=st.integers(-10000, 10000))
@settings(max_examples=200)
def test_number_validate_int(value):
    """NumberPrompt should accept any int."""
    p = NumberPrompt("q")
    result = p._validate_answer(value)
    assert result == value


@given(
    value=st.integers(-100, 100),
    lo=st.integers(-50, 0),
    hi=st.integers(0, 50),
)
@settings(max_examples=200)
def test_number_min_max_consistency(value, lo, hi):
    """If value is in [lo, hi], accept; otherwise reject."""
    if lo > hi:
        return
    p = NumberPrompt("q", min=lo, max=hi)
    try:
        result = p._validate_answer(value)
        assert lo <= result <= hi
    except ValidationError:
        assert value < lo or value > hi


# ── Confirm: coercion properties ──


@given(value=st.one_of(st.booleans(), st.sampled_from(["y", "yes", "n", "no", "true", "false", "1", "0", "Y", "YES"])))
@settings(max_examples=100)
def test_confirm_validate_never_raises(value):
    """ConfirmPrompt._validate_answer should handle any bool-ish input."""
    p = ConfirmPrompt("q")
    result = p._validate_answer(value)
    assert isinstance(result, bool)


# ── Checkbox: validate invariant ──


@given(
    choices=st.lists(choice_name, min_size=2, max_size=8, unique=True),
    selected_indices=st.lists(st.integers(0, 7), max_size=5),
)
@settings(max_examples=200)
def test_checkbox_validate_subset(choices, selected_indices):
    """CheckboxPrompt should accept any subset of valid choices."""
    valid_indices = [i % len(choices) for i in selected_indices]
    selected = list({choices[i] for i in valid_indices})
    p = CheckboxPrompt("q", choices=choices)
    result = p._validate_answer(selected)
    assert set(result) <= set(choices)


# ── Agent protocol: all prompts emit valid JSON ──


def _agent_dict_valid(prompt_cls, **kwargs):
    """Agent dict should always be valid JSON-serializable."""
    p = prompt_cls("test message", **kwargs)
    d = p._to_agent_dict()
    serialized = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert parsed["type"] == p.prompt_type
    assert parsed["message"] == "test message"
    return parsed


def test_all_prompts_agent_dict_roundtrip():
    """Every prompt type should produce a valid, roundtrippable agent dict."""
    _agent_dict_valid(TextPrompt)
    _agent_dict_valid(ConfirmPrompt)
    _agent_dict_valid(SelectPrompt, choices=["a", "b"])
    _agent_dict_valid(CheckboxPrompt, choices=["a", "b"])
    _agent_dict_valid(NumberPrompt)
    d = _agent_dict_valid(RawlistPrompt, choices=["a", "b"])
    assert "choices" in d
    d = _agent_dict_valid(ExpandPrompt, choices=[{"key": "y", "name": "Yes", "value": True}])
    assert "choices" in d


# ── Cursor navigation: property tests ──


@given(
    num_enabled=st.integers(1, 10),
    num_disabled=st.integers(0, 5),
    num_separators=st.integers(0, 3),
    steps=st.lists(st.sampled_from([-1, 1]), min_size=1, max_size=50),
)
@settings(max_examples=300)
def test_cursor_always_lands_on_selectable(num_enabled, num_disabled, num_separators, steps):
    """_move_cursor should never land on a disabled choice or separator."""
    items: list[str | Choice[str] | Separator] = []
    for i in range(num_enabled):
        items.append(f"enabled_{i}")
    for i in range(num_disabled):
        items.append(Choice(f"disabled_{i}", f"d{i}", disabled=True))
    for _ in range(num_separators):
        items.append(Separator())

    if not items:
        return

    p = SelectPrompt("q", choices=items)
    selectable = p._selectable_indices()
    assert len(selectable) == num_enabled

    cursor = selectable[0]
    for direction in steps:
        cursor = p._move_cursor(cursor, direction)
        assert cursor in selectable, f"Cursor {cursor} not in selectable {selectable}"


@given(
    num_choices=st.integers(1, 15),
    steps=st.integers(0, 100),
)
@settings(max_examples=100)
def test_cursor_loop_wraps(num_choices, steps):
    """With loop=True, cursor should wrap around."""
    choices = [f"c{i}" for i in range(num_choices)]
    p = SelectPrompt("q", choices=choices)
    cursor = 0
    for _ in range(steps):
        cursor = p._move_cursor(cursor, 1)
    assert 0 <= cursor < num_choices


@given(
    num_choices=st.integers(2, 10),
    steps=st.integers(1, 50),
)
@settings(max_examples=100)
def test_cursor_no_loop_clamps(num_choices, steps):
    """With loop=False, moving forward enough should clamp at last index."""
    choices = [f"c{i}" for i in range(num_choices)]
    p = SelectPrompt("q", choices=choices, loop=False)
    cursor = 0
    for _ in range(steps):
        cursor = p._move_cursor(cursor, 1)
    assert cursor == min(steps, num_choices - 1)


@given(
    num_choices=st.integers(2, 10),
    steps=st.integers(1, 50),
)
@settings(max_examples=100)
def test_cursor_no_loop_clamps_backward(num_choices, steps):
    """With loop=False, moving backward from start should stay at 0."""
    choices = [f"c{i}" for i in range(num_choices)]
    p = SelectPrompt("q", choices=choices, loop=False)
    cursor = 0
    for _ in range(steps):
        cursor = p._move_cursor(cursor, -1)
    assert cursor == 0
