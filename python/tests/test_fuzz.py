"""Fuzz tests using hypothesis to generate truly random/malformed inputs.

Complements test_property.py (structured property-based tests) and
test_chaos.py (hand-crafted edge cases) by throwing arbitrary junk at
every public validation surface and the agent protocol layer.
"""

from __future__ import annotations

import contextlib
import io
import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import InvalidChoiceError, PromptAbortedError, ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

# ── 1. Fuzz NumberPrompt._validate_answer ──


@given(
    value=st.one_of(
        st.floats(allow_nan=True, allow_infinity=True),
        st.text(),
        st.integers(),
        st.booleans(),
        st.none(),
        st.binary(),
        st.lists(st.integers()),
    )
)
@settings(max_examples=500)
def test_fuzz_number_validate_no_crash(value: object) -> None:
    """NumberPrompt._validate_answer should never crash on any input type."""
    p = NumberPrompt("q")
    with contextlib.suppress(ValidationError, TypeError):
        p._validate_answer(value)


# ── 2. Fuzz Choice.from_raw ──


@given(
    raw=st.one_of(
        st.text(),
        st.dictionaries(st.text(), st.text(), min_size=0, max_size=5),
        st.integers(),
        st.booleans(),
        st.none(),
    )
)
@settings(max_examples=500)
def test_fuzz_choice_from_raw_no_crash(raw: object) -> None:
    """Choice.from_raw should handle any input without crashing."""
    with contextlib.suppress(InvalidChoiceError, TypeError):
        Choice.from_raw(raw)  # type: ignore[arg-type]


# ── 3. Fuzz JSON agent protocol ──


@given(payload=st.text())
@settings(max_examples=500)
def test_fuzz_agent_json_no_crash(payload: str) -> None:
    """Agent mode should handle any stdin content without crashing."""
    mp = pytest.MonkeyPatch()
    try:
        mp.setenv("INQUIRER_AI_MODE", "agent")
        mp.setattr("sys.stdin", io.StringIO(payload + "\n"))
        mp.setattr("sys.stdout", io.StringIO())
        p = TextPrompt("q")
        with contextlib.suppress(ValidationError, PromptAbortedError):
            p.execute()
    finally:
        mp.undo()


# ── 4. Fuzz ConfirmPrompt._validate_answer ──


@given(
    value=st.one_of(
        st.booleans(),
        st.text(),
        st.integers(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.none(),
    )
)
@settings(max_examples=500)
def test_fuzz_confirm_validate_no_crash(value: object) -> None:
    """ConfirmPrompt._validate_answer should never crash and always return bool."""
    p = ConfirmPrompt("q")
    result = p._validate_answer(value)
    assert isinstance(result, bool)


# ── 5. Fuzz SelectPrompt._validate_answer ──


@given(
    choices=st.lists(st.text(min_size=1), min_size=1, max_size=10, unique=True),
    answer=st.text(),
)
@settings(max_examples=500)
def test_fuzz_select_validate(choices: list[str], answer: str) -> None:
    """SelectPrompt should accept valid choices and reject invalid ones cleanly."""
    p = SelectPrompt("q", choices=choices)
    try:
        result = p._validate_answer(answer)
        assert result in choices
    except ValidationError:
        assert answer not in choices


# ── 6. Fuzz TextPrompt.execute() in agent mode ──


@given(answer=st.one_of(st.text(), st.integers(), st.booleans(), st.none()))
@settings(max_examples=500)
def test_fuzz_text_execute_agent(answer: object) -> None:
    """TextPrompt.execute() in agent mode should handle any answer type."""
    mp = pytest.MonkeyPatch()
    try:
        mp.setenv("INQUIRER_AI_MODE", "agent")
        mp.setattr("sys.stdin", io.StringIO(json.dumps({"answer": answer}) + "\n"))
        mp.setattr("sys.stdout", io.StringIO())
        p = TextPrompt("q")
        result = p.execute()
        assert isinstance(result, str)
    finally:
        mp.undo()


# ── 7. Fuzz NumberPrompt with NaN / Infinity edge cases ──


@given(
    value=st.floats(allow_nan=True, allow_infinity=True),
    min_val=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10)),
    max_val=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10)),
)
@settings(max_examples=500)
def test_fuzz_number_with_bounds(value: float, min_val: float | None, max_val: float | None) -> None:
    """NumberPrompt with random bounds should never crash."""
    p = NumberPrompt("q", min=min_val, max=max_val)
    try:
        result = p._validate_answer(value)
        # If we got a result, verify bounds are respected (when both are finite)
        if min_val is not None and not math.isnan(result):
            assert result >= min_val
        if max_val is not None and not math.isnan(result):
            assert result <= max_val
    except ValidationError:
        pass  # expected for out-of-range or NaN/Inf


# ── 8. Fuzz CheckboxPrompt._validate_answer ──


@given(
    choices=st.lists(st.text(min_size=1), min_size=1, max_size=10, unique=True),
    answer=st.lists(st.text(), max_size=5),
)
@settings(max_examples=500)
def test_fuzz_checkbox_validate(choices: list[str], answer: list[str]) -> None:
    """CheckboxPrompt._validate_answer should handle any list input cleanly."""
    p = CheckboxPrompt("q", choices=choices)
    try:
        result = p._validate_answer(answer)
        assert isinstance(result, list)
        assert all(v in choices for v in result)
    except ValidationError:
        # At least one answer was not in the choices
        pass


# ── 9. Fuzz CheckboxPrompt._validate_answer with non-list inputs ──


@given(
    value=st.one_of(
        st.text(),
        st.integers(),
        st.booleans(),
        st.none(),
        st.dictionaries(st.text(), st.text()),
    )
)
@settings(max_examples=500)
def test_fuzz_checkbox_validate_non_list(value: object) -> None:
    """CheckboxPrompt._validate_answer should reject non-list inputs."""
    p = CheckboxPrompt("q", choices=["a", "b", "c"])
    with contextlib.suppress(ValidationError, TypeError):
        p._validate_answer(value)


# ── 10. Fuzz agent protocol with structurally varied JSON ──


@given(
    data=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
        st.lists(st.integers(), max_size=5),
        st.dictionaries(st.text(), st.one_of(st.text(), st.integers(), st.none()), max_size=5),
    )
)
@settings(max_examples=500)
def test_fuzz_agent_structured_json(data: object) -> None:
    """Agent mode should handle any valid JSON value without crashing."""
    mp = pytest.MonkeyPatch()
    try:
        mp.setenv("INQUIRER_AI_MODE", "agent")
        mp.setattr("sys.stdin", io.StringIO(json.dumps(data) + "\n"))
        mp.setattr("sys.stdout", io.StringIO())
        p = TextPrompt("q")
        with contextlib.suppress(ValidationError, PromptAbortedError):
            p.execute()
    finally:
        mp.undo()


# ── 11. Fuzz NumberPrompt string parsing ──


@given(value=st.text())
@settings(max_examples=500)
def test_fuzz_number_from_string(value: str) -> None:
    """NumberPrompt should parse or reject any string without crashing."""
    p = NumberPrompt("q")
    try:
        result = p._validate_answer(value)
        assert isinstance(result, (int, float))
    except ValidationError:
        pass  # expected for non-numeric strings


# ── 12. Fuzz TextPrompt._validate_answer ──


@given(
    value=st.one_of(
        st.text(),
        st.integers(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.booleans(),
        st.none(),
        st.binary(),
        st.lists(st.text()),
    )
)
@settings(max_examples=500)
def test_fuzz_text_validate_no_crash(value: object) -> None:
    """TextPrompt._validate_answer should convert anything to str without crashing."""
    p = TextPrompt("q")
    result = p._validate_answer(value)
    assert isinstance(result, str)
