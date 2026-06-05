"""Cross-language consistency tests.

These tests verify that Python's behavior matches Go, TypeScript, and Rust
implementations.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from inquirer_ai.choice import Choice, value_matches
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.choice_base import ChoiceBasePrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.rawlist import RawlistPrompt
from inquirer_ai.prompts.select import SelectPrompt

# ── Helpers ──


def coerce_bool(value):
    """Shorthand: run ConfirmPrompt._validate_answer on a value."""
    return ConfirmPrompt("q")._validate_answer(value)


def validate_number(value, *, min=None, max=None, float_allowed=True):
    """Shorthand: run NumberPrompt._validate_answer on a value."""
    return NumberPrompt("q", min=min, max=max, float_allowed=float_allowed)._validate_answer(value)


# ══════════════════════════════════════════════════════════════════════════════
# 1. coerce_bool edge cases
# ══════════════════════════════════════════════════════════════════════════════


class TestCoerceBoolCrossLanguage:
    """Verify coerce_bool matches cross-language consensus.

    Go/TS/Rust all agree: NaN and Inf are not valid boolean concepts
    and should coerce to False.
    """

    # ── Values that should coerce to False ──

    def test_nan_is_false(self):
        assert coerce_bool(float("nan")) is False

    def test_inf_is_false(self):
        assert coerce_bool(float("inf")) is False

    def test_neg_inf_is_false(self):
        assert coerce_bool(float("-inf")) is False

    def test_none_is_false(self):
        assert coerce_bool(None) is False

    def test_zero_int_is_false(self):
        assert coerce_bool(0) is False

    def test_zero_float_is_false(self):
        assert coerce_bool(0.0) is False

    def test_empty_string_is_false(self):
        # Empty string through bool() is False, but _validate_answer
        # checks isinstance(str) first -> "".lower() not in ("y","yes","true","1")
        assert coerce_bool("") is False

    def test_empty_list_is_false(self):
        assert coerce_bool([]) is False

    def test_empty_dict_is_false(self):
        assert coerce_bool({}) is False

    def test_false_is_false(self):
        assert coerce_bool(False) is False

    def test_string_0_is_false(self):
        assert coerce_bool("0") is False

    def test_string_false_is_false(self):
        assert coerce_bool("false") is False

    def test_string_no_is_false(self):
        assert coerce_bool("no") is False

    def test_string_n_is_false(self):
        assert coerce_bool("n") is False

    # ── Values that should coerce to True ──

    def test_true_is_true(self):
        assert coerce_bool(True) is True

    def test_one_int_is_true(self):
        assert coerce_bool(1) is True

    def test_neg_one_int_is_true(self):
        assert coerce_bool(-1) is True

    def test_half_float_is_true(self):
        assert coerce_bool(0.5) is True

    def test_string_yes_is_true(self):
        assert coerce_bool("yes") is True

    def test_string_y_is_true(self):
        assert coerce_bool("y") is True

    def test_string_true_is_true(self):
        assert coerce_bool("true") is True

    def test_string_1_is_true(self):
        assert coerce_bool("1") is True


# ══════════════════════════════════════════════════════════════════════════════
# 2. validate_number NaN/Inf rejection
# ══════════════════════════════════════════════════════════════════════════════


class TestValidateNumberNanInf:
    """Go, TypeScript, and Rust all reject NaN and Inf in number validation.

    Python currently accepts them. These tests assert the CORRECT behavior
    (rejection) and are expected to FAIL on the current code, exposing the bug.
    """

    # ── Direct numeric NaN/Inf (the main bug) ──

    def test_nan_rejected(self):
        with pytest.raises(ValidationError):
            validate_number(float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(ValidationError):
            validate_number(float("inf"))

    def test_neg_inf_rejected(self):
        with pytest.raises(ValidationError):
            validate_number(float("-inf"))

    # ── String forms (these ARE rejected because int() parsing fails) ──

    def test_string_nan_rejected(self):
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number("NaN")

    def test_string_infinity_rejected(self):
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number("Infinity")

    def test_string_neg_infinity_rejected(self):
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number("-Infinity")

    # ── NaN silently passes min/max bounds (consequence of the main bug) ──

    def test_nan_not_in_bounds(self):
        """NaN should be rejected even with bounds, not silently accepted."""
        with pytest.raises(ValidationError):
            validate_number(float("nan"), min=0, max=100)

    def test_inf_rejected_with_max_bound(self):
        """Inf is rejected before bounds check."""
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number(float("inf"), max=1000)

    def test_neg_inf_rejected_with_min_bound(self):
        """-Inf is rejected before bounds check."""
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number(float("-inf"), min=-1000)

    # ── NaN with float_allowed=False (another consequence) ──

    def test_nan_with_float_not_allowed(self):
        """NaN should be rejected with ValidationError, not crash with ValueError."""
        with pytest.raises(ValidationError):
            validate_number(float("nan"), float_allowed=False)

    # ── Normal numbers still work ──

    def test_positive_int(self):
        assert validate_number(42) == 42

    def test_negative_int(self):
        assert validate_number(-7) == -7

    def test_zero(self):
        assert validate_number(0) == 0

    def test_positive_float(self):
        assert validate_number(3.14) == pytest.approx(3.14)

    def test_negative_float(self):
        assert validate_number(-2.5) == pytest.approx(-2.5)

    def test_min_boundary_accept(self):
        assert validate_number(5, min=5) == 5

    def test_min_boundary_reject(self):
        with pytest.raises(ValidationError, match="at least"):
            validate_number(4, min=5)

    def test_max_boundary_accept(self):
        assert validate_number(10, max=10) == 10

    def test_max_boundary_reject(self):
        with pytest.raises(ValidationError, match="at most"):
            validate_number(11, max=10)

    def test_within_range(self):
        assert validate_number(50, min=0, max=100) == 50

    def test_string_integer(self):
        assert validate_number("99") == 99

    def test_string_float(self):
        assert validate_number("3.14") == pytest.approx(3.14)

    def test_string_garbage_rejected(self):
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number("abc")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Property-based tests (Hypothesis)
# ══════════════════════════════════════════════════════════════════════════════


class TestCoerceBoolProperties:
    """Property-based tests for coerce_bool."""

    @given(
        value=st.one_of(
            st.booleans(),
            st.integers(-1000, 1000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=50),
            st.none(),
            st.lists(st.integers(), max_size=5),
            st.dictionaries(st.text(max_size=5), st.integers(), max_size=3),
        )
    )
    @settings(max_examples=300)
    def test_always_returns_bool(self, value):
        """coerce_bool must always return a bool, never raise."""
        result = coerce_bool(value)
        assert isinstance(result, bool)

    @given(
        value=st.one_of(
            st.booleans(),
            st.integers(-1000, 1000),
            st.text(max_size=50),
            st.none(),
        )
    )
    @settings(max_examples=300)
    def test_idempotent(self, value):
        """coerce_bool(coerce_bool(x)) == coerce_bool(x) for all x."""
        first = coerce_bool(value)
        second = coerce_bool(first)
        assert second == first


class TestValidateNumberProperties:
    """Property-based tests for validate_number."""

    @given(value=st.one_of(st.integers(-10000, 10000), st.floats(allow_nan=False, allow_infinity=False)))
    @settings(max_examples=300)
    def test_valid_result_is_number(self, value):
        """If validate_number succeeds, the result is int or float."""
        result = validate_number(value)
        assert isinstance(result, (int, float))
        assert not isinstance(result, bool)

    @given(value=st.integers(-10000, 10000))
    @settings(max_examples=200)
    def test_float_not_allowed_returns_int(self, value):
        """When float_allowed=False, valid results are always int."""
        result = validate_number(value, float_allowed=False)
        assert isinstance(result, int)

    @given(
        value=st.integers(-100, 100),
        lo=st.integers(-50, 0),
        hi=st.integers(0, 50),
    )
    @settings(max_examples=300)
    def test_result_within_bounds(self, value, lo, hi):
        """If validate_number accepts, result is within [min, max]."""
        if lo > hi:
            return
        try:
            result = validate_number(value, min=lo, max=hi)
            assert lo <= result <= hi
        except ValidationError:
            assert value < lo or value > hi

    @given(
        value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        lo=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e3, max_value=0),
        hi=st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=1e3),
    )
    @settings(max_examples=200)
    def test_float_result_within_bounds(self, value, lo, hi):
        """Float values accepted by validate_number respect [min, max]."""
        if lo > hi:
            return
        try:
            result = validate_number(value, min=lo, max=hi)
            assert lo <= result <= hi
        except ValidationError:
            assert value < lo or value > hi

    @given(value=st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_finite_floats_always_accepted(self, value):
        """Any finite float should be accepted when float_allowed=True."""
        result = validate_number(value)
        assert isinstance(result, (int, float))
        assert math.isfinite(result)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Numeric-string grammar (R2) — identical accept/reject across all 4 languages
# ══════════════════════════════════════════════════════════════════════════════


class TestNumberGrammarCrossLanguage:
    """All four implementations apply the same numeric-string grammar (R2)."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("1e3", 1000), ("  5  ", 5), ("3.5", 3.5), ("-2", -2), ("1E-3", 0.001)],
    )
    def test_accepts(self, text, expected):
        assert validate_number(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["1_000", "3abc", "0x10", ".5", "5.", "", "+"])
    def test_rejects(self, text):
        with pytest.raises(ValidationError, match="Not a valid number"):
            validate_number(text)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Type-aware value matching (R4) — string/number/bool never cross-match
# ══════════════════════════════════════════════════════════════════════════════


class TestTypedValueMatchingCrossLanguage:
    def test_string_never_matches_number(self):
        assert not value_matches("42", 42)

    def test_bool_never_matches_number(self):
        assert not value_matches(True, 1)
        assert not value_matches(0, False)

    def test_select_typed(self):
        p = SelectPrompt("q", choices=[Choice(name="zero", value=0)])
        assert p._validate_answer(0) == 0
        with pytest.raises(ValidationError):
            p._validate_answer(False)

    def test_rawlist_index_not_bool(self):
        p = RawlistPrompt("q", choices=["a", "b"])
        assert p._validate_answer(1) == "a"
        with pytest.raises(ValidationError):
            p._validate_answer(True)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Viewport scroll window — the centered, clamped page that select / checkbox
#    / rawlist / expand render around the cursor. All four languages compute the
#    same [start, end) for a given (cursor, total, page_size); the reference is
#    Go ``visibleRange``. This golden table is replicated verbatim in
#    go/prompt/tui_boundary_test.go, typescript/tests/cross-language.test.ts and
#    rust/src/prompts/select.rs — if any implementation drifts, its own copy of
#    this table reddens. Oracle: spec formula
#    ``ps = min(page_size, total); start = clamp(cursor - ps//2, 0, total - ps)``.
# ══════════════════════════════════════════════════════════════════════════════


# (cursor, total, page_size, expected_start, expected_end)
VIEWPORT_GOLDEN = [
    (0, 3, 10, 0, 3),  # total < page_size: no scroll
    (2, 3, 10, 0, 3),  # total < page_size: centered cursor still no scroll
    (0, 10, 10, 0, 10),  # total == page_size
    (0, 20, 10, 0, 10),  # cursor at top
    (5, 20, 10, 0, 10),  # cursor == floor(ps/2): still pinned to 0
    (6, 20, 10, 1, 11),  # first scroll — off-by-one sentinel
    (15, 20, 10, 10, 20),  # centered mid-list
    (19, 20, 10, 10, 20),  # near end: clamped to total - ps
    (5, 12, 3, 4, 7),  # odd page_size, floor(3/2) == 1
    (5, 12, 4, 3, 7),  # even page_size, floor(4/2) == 2
    (7, 10, 1, 7, 8),  # page_size == 1
    (99, 100, 10, 90, 100),  # end clamp
    (50, 100, 10, 45, 55),  # mid large list
    (0, 0, 5, 0, 0),  # empty list (defensive: rejected upstream, must not crash)
]


class TestViewportWindowCrossLanguage:
    @pytest.mark.parametrize(("cursor", "total", "page_size", "start", "end"), VIEWPORT_GOLDEN)
    def test_window(self, cursor, total, page_size, start, end):
        assert ChoiceBasePrompt._visible_window(cursor, total, page_size) == (start, end)

    def test_window_never_exceeds_page_size(self):
        # Span is min(page_size, total) for every reachable state — the window
        # never shows more rows than the page allows, nor more than exist.
        for total in range(0, 25):
            for page_size in (1, 3, 4, 10):
                for cursor in range(0, max(total, 1)):
                    s, e = ChoiceBasePrompt._visible_window(cursor, total, page_size)
                    assert 0 <= s <= e <= total
                    assert e - s == min(page_size, total)

    def test_cursor_stays_inside_window(self):
        # The whole point of centering: a valid cursor is always visible.
        for total in range(1, 25):
            for page_size in (1, 3, 4, 10):
                for cursor in range(total):
                    s, e = ChoiceBasePrompt._visible_window(cursor, total, page_size)
                    assert s <= cursor < e
