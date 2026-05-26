"""Tests for the callback execution order invariant: validate -> filter.

The critical invariant is:
  1. Built-in validation runs first (e.g., _validate_answer)
  2. User-provided validate callback runs second
  3. Filter runs LAST, only on accepted values
"""

import io
import json

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.expand import ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


def _agent_env(monkeypatch, answers):
    """Set up agent mode with the given list of answer dicts."""
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    lines = "".join(json.dumps(a) + "\n" for a in answers)
    monkeypatch.setattr("sys.stdin", io.StringIO(lines))
    monkeypatch.setattr("sys.stdout", io.StringIO())


# ── Test 1: Order invariant — validate is called before filter ──


class TestOrderInvariant:
    def test_text_validate_before_filter(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "hello"}])
        log = []
        p = TextPrompt(
            "Q",
            validate=lambda v: (log.append("validate"), True)[1],
            filter=lambda v: (log.append("filter"), v)[1],
        )
        p.execute()
        assert log == ["validate", "filter"]

    def test_number_validate_before_filter(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": 42}])
        log = []
        p = NumberPrompt(
            "Q",
            validate=lambda v: (log.append("validate"), True)[1],
            filter=lambda v: (log.append("filter"), v)[1],
        )
        p.execute()
        assert log == ["validate", "filter"]

    def test_select_validate_before_filter(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "a"}])
        log = []
        p = SelectPrompt(
            "Q",
            choices=[{"name": "A", "value": "a"}],
            validate=lambda v: (log.append("validate"), True)[1],
            filter=lambda v: (log.append("filter"), v)[1],
        )
        p.execute()
        assert log == ["validate", "filter"]

    def test_expand_validate_before_filter(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "y"}])
        log = []
        p = ExpandPrompt(
            "Q",
            choices=[{"key": "y", "name": "Yes", "value": "yes"}],
            validate=lambda v: (log.append("validate"), True)[1],
            filter=lambda v: (log.append("filter"), v)[1],
        )
        p.execute()
        assert log == ["validate", "filter"]

    def test_checkbox_validate_before_filter(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": ["a"]}])
        log = []
        p = CheckboxPrompt(
            "Q",
            choices=[{"name": "A", "value": "a"}],
            validate=lambda v: (log.append("validate"), True)[1],
            filter=lambda v: (log.append("filter"), v)[1],
        )
        p.execute()
        assert log == ["validate", "filter"]


# ── Test 2: Filter NOT called when validate rejects ──


class TestFilterNotCalledOnRejection:
    def test_text_filter_skipped_on_rejection(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "bad"}] * 3)
        filter_called = []
        p = TextPrompt(
            "Q",
            validate=lambda v: "rejected",
            filter=lambda v: (filter_called.append(True), v)[1],
        )
        with pytest.raises(ValidationError):
            p.execute()
        assert filter_called == [], "filter must NOT be called when validate rejects"

    def test_number_filter_skipped_on_user_rejection(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": 42}] * 3)
        filter_called = []
        p = NumberPrompt(
            "Q",
            validate=lambda v: "rejected",
            filter=lambda v: (filter_called.append(True), v)[1],
        )
        with pytest.raises(ValidationError):
            p.execute()
        assert filter_called == [], "filter must NOT be called when validate rejects"

    def test_select_filter_skipped_on_rejection(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "a"}] * 3)
        filter_called = []
        p = SelectPrompt(
            "Q",
            choices=[{"name": "A", "value": "a"}],
            validate=lambda v: "rejected",
            filter=lambda v: (filter_called.append(True), v)[1],
        )
        with pytest.raises(ValidationError):
            p.execute()
        assert filter_called == [], "filter must NOT be called when validate rejects"

    def test_number_filter_skipped_on_builtin_rejection(self, monkeypatch):
        """When built-in validation rejects (e.g., out of range), neither
        user validate nor filter should be called."""
        _agent_env(monkeypatch, [{"answer": 100}] * 3)
        filter_called = []
        validate_called = []
        p = NumberPrompt(
            "Q",
            min=0,
            max=10,
            validate=lambda v: (validate_called.append(True), True)[1],
            filter=lambda v: (filter_called.append(True), v)[1],
        )
        with pytest.raises(ValidationError):
            p.execute()
        assert filter_called == [], "filter must NOT be called when built-in rejects"
        assert validate_called == [], "user validate must NOT be called when built-in rejects"


# ── Test 3: Filter receives the raw (pre-filter) value ──


class TestFilterSeesRawValue:
    def test_text_filter_receives_original(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": "  HELLO  "}])
        received = []
        p = TextPrompt(
            "Q",
            validate=lambda v: True,
            filter=lambda v: (received.append(v), v.strip())[1],
        )
        result = p.execute()
        assert received == ["  HELLO  "], "filter should receive the raw value"
        assert result == "HELLO", "result should be the filtered value"

    def test_number_filter_receives_validated_number(self, monkeypatch):
        _agent_env(monkeypatch, [{"answer": 42}])
        received = []
        p = NumberPrompt(
            "Q",
            validate=lambda v: True,
            filter=lambda v: (received.append(v), v * 2)[1],
        )
        result = p.execute()
        assert received == [42], "filter should receive the number after built-in validation"
        assert result == 84


# ── Test 4: Multiple rejections, filter called only once (on accepted value) ──


class TestMultipleRejectionsFilterCalledOnce:
    def test_text_filter_once_after_retries(self, monkeypatch):
        _agent_env(
            monkeypatch,
            [
                {"answer": "bad1"},
                {"answer": "bad2"},
                {"answer": "good"},
            ],
        )
        filter_calls = []
        attempt = [0]

        def validate(v):
            attempt[0] += 1
            return True if attempt[0] > 2 else "rejected"

        p = TextPrompt(
            "Q",
            validate=validate,
            filter=lambda v: (filter_calls.append(v), v + "_ok")[1],
        )
        result = p.execute()
        assert filter_calls == ["good"], "filter should only be called on the accepted value"
        assert result == "good_ok"

    def test_number_filter_once_after_retries(self, monkeypatch):
        _agent_env(
            monkeypatch,
            [
                {"answer": 1},
                {"answer": 2},
                {"answer": 3},
            ],
        )
        filter_calls = []
        attempt = [0]

        def validate(v):
            attempt[0] += 1
            return True if attempt[0] > 2 else "rejected"

        p = NumberPrompt(
            "Q",
            validate=validate,
            filter=lambda v: (filter_calls.append(v), v * 10)[1],
        )
        result = p.execute()
        assert filter_calls == [3], "filter should only be called on the accepted value"
        assert result == 30

    def test_select_filter_once_after_retries(self, monkeypatch):
        _agent_env(
            monkeypatch,
            [
                {"answer": "a"},
                {"answer": "a"},
                {"answer": "a"},
            ],
        )
        filter_calls = []
        attempt = [0]

        def validate(v):
            attempt[0] += 1
            return True if attempt[0] > 2 else "rejected"

        p = SelectPrompt(
            "Q",
            choices=[{"name": "A", "value": "a"}],
            validate=validate,
            filter=lambda v: (filter_calls.append(v), v)[1],
        )
        p.execute()
        assert len(filter_calls) == 1, f"filter should be called once, got {len(filter_calls)}"


# ── Test 5: Cross-type consistency ──


class TestCrossTypeConsistency:
    """The same validate->filter order must hold across all prompt types."""

    @pytest.mark.parametrize(
        "prompt_type,prompt_factory,answer",
        [
            (
                "Text",
                lambda log: TextPrompt(
                    "Q",
                    validate=lambda v: (log.append("validate"), True)[1],
                    filter=lambda v: (log.append("filter"), v)[1],
                ),
                {"answer": "x"},
            ),
            (
                "Number",
                lambda log: NumberPrompt(
                    "Q",
                    validate=lambda v: (log.append("validate"), True)[1],
                    filter=lambda v: (log.append("filter"), v)[1],
                ),
                {"answer": 5},
            ),
            (
                "Select",
                lambda log: SelectPrompt(
                    "Q",
                    choices=[{"name": "X", "value": "x"}],
                    validate=lambda v: (log.append("validate"), True)[1],
                    filter=lambda v: (log.append("filter"), v)[1],
                ),
                {"answer": "x"},
            ),
            (
                "Expand",
                lambda log: ExpandPrompt(
                    "Q",
                    choices=[{"key": "y", "name": "Yes", "value": "yes"}],
                    validate=lambda v: (log.append("validate"), True)[1],
                    filter=lambda v: (log.append("filter"), v)[1],
                ),
                {"answer": "y"},
            ),
            (
                "Checkbox",
                lambda log: CheckboxPrompt(
                    "Q",
                    choices=[{"name": "A", "value": "a"}],
                    validate=lambda v: (log.append("validate"), True)[1],
                    filter=lambda v: (log.append("filter"), v)[1],
                ),
                {"answer": ["a"]},
            ),
        ],
    )
    def test_validate_before_filter(self, monkeypatch, prompt_type, prompt_factory, answer):
        _agent_env(monkeypatch, [answer])
        log = []
        prompt = prompt_factory(log)
        prompt.execute()
        assert log == ["validate", "filter"], f"{prompt_type}: expected [validate, filter], got {log}"
