"""Protocol contract tests for the inquirer-ai agent JSON line protocol.

These tests verify the exact shape of every protocol message emitted by the
Python implementation.  They do NOT test TUI behaviour -- only the agent
protocol JSON format.

Sections
--------
1. Handshake message format
2. Prompt message format for each prompt type
3. Validation error format
4. Answer extraction and malformed JSON handling
5. Retry invariant (re-sent prompt after validation_error)
6. Property-based (hypothesis) tests
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import inquirer_ai.prompts.base as _base
from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.expand import ExpandChoice, ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.search import SearchPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

HANDSHAKE_REQUIRED_FIELDS = {
    "kind": str,
    "protocol": str,
    "version": str,
    "format": str,
    "interaction": str,
    "total": type(None),
    "description": str,
    "example_response": dict,
}


def _agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure environment for agent mode."""
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")


def _capture_stdout(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Redirect sys.stdout to a StringIO and return it."""
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    return buf


def _feed_stdin(monkeypatch: pytest.MonkeyPatch, lines: list[dict[str, Any]]) -> None:
    """Set sys.stdin to a StringIO containing newline-delimited JSON."""
    payload = "\n".join(json.dumps(line) for line in lines) + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


def _collect_stdout_dicts(buf: io.StringIO) -> list[dict[str, Any]]:
    """Parse all JSON lines written to the captured stdout."""
    result: list[dict[str, Any]] = []
    for line in buf.getvalue().strip().splitlines():
        result.append(json.loads(line))
    return result


def _extract_handshake(dicts: list[dict[str, Any]]) -> dict[str, Any]:
    for d in dicts:
        if d.get("kind") == "handshake":
            return d
    raise AssertionError("No handshake found in stdout output")


def _extract_prompts(dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in dicts if d.get("kind") == "prompt"]


# ══════════════════════════════════════════════════════════════════════════════
# 1. Handshake message format
# ══════════════════════════════════════════════════════════════════════════════


class TestHandshakeFormat:
    """The first message on stdout in agent mode must be a well-formed handshake."""

    def test_handshake_has_all_required_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "x"}])

        TextPrompt("Name?").execute()

        dicts = _collect_stdout_dicts(buf)
        hs = _extract_handshake(dicts)
        for field, expected_type in HANDSHAKE_REQUIRED_FIELDS.items():
            assert field in hs, f"Missing handshake field: {field}"
            if expected_type is type(None):
                assert hs[field] is None, f"Field {field} should be None, got {hs[field]!r}"
            else:
                assert isinstance(hs[field], expected_type), (
                    f"Field {field}: expected {expected_type.__name__}, got {type(hs[field]).__name__}"
                )

    def test_handshake_exact_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "x"}])

        TextPrompt("Name?").execute()

        hs = _extract_handshake(_collect_stdout_dicts(buf))
        assert hs["kind"] == "handshake"
        assert hs["protocol"] == "inquirer-ai"
        assert isinstance(hs["version"], str) and len(hs["version"]) > 0
        assert hs["format"] == "jsonl"
        assert hs["interaction"] == "sequential"
        assert hs["total"] is None
        assert isinstance(hs["description"], str) and len(hs["description"]) > 0
        assert hs["example_response"] == {"answer": "<value>"}

    def test_handshake_is_first_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "x"}])

        TextPrompt("Name?").execute()

        dicts = _collect_stdout_dicts(buf)
        assert dicts[0]["kind"] == "handshake"

    def test_handshake_sent_only_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "a"}, {"answer": "b"}])

        TextPrompt("Q1?").execute()
        TextPrompt("Q2?").execute()

        dicts = _collect_stdout_dicts(buf)
        handshakes = [d for d in dicts if d.get("kind") == "handshake"]
        assert len(handshakes) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 2. Prompt message format for each prompt type
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_REQUIRED_FIELDS = {"kind", "type", "message", "default", "step", "total"}


class TestTextPromptFormat:
    def test_agent_dict_fields(self) -> None:
        _base._agent_step = 1
        d = TextPrompt("What is your name?")._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "input"
        assert d["message"] == "What is your name?"
        assert d["default"] is None
        assert d["step"] == 1
        assert d["total"] is None
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_agent_dict_with_default(self) -> None:
        d = TextPrompt("Name?", default="Alice")._to_agent_dict()
        assert d["default"] == "Alice"

    def test_agent_dict_is_json_serializable(self) -> None:
        d = TextPrompt("Name?", default="Bob")._to_agent_dict()
        serialized = json.dumps(d)
        assert json.loads(serialized) == d


class TestConfirmPromptFormat:
    def test_agent_dict_fields(self) -> None:
        d = ConfirmPrompt("Continue?")._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "confirm"
        assert d["message"] == "Continue?"
        assert d["default"] is False
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_agent_dict_default_true(self) -> None:
        d = ConfirmPrompt("Sure?", default=True)._to_agent_dict()
        assert d["default"] is True


class TestSelectPromptFormat:
    def test_agent_dict_fields(self) -> None:
        d = SelectPrompt("Pick one", choices=["a", "b", "c"])._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "select"
        assert d["message"] == "Pick one"
        assert "choices" in d
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_choices_structure(self) -> None:
        d = SelectPrompt("Pick", choices=["alpha", "beta"])._to_agent_dict()
        assert d["choices"] == [
            {"name": "alpha", "value": "alpha"},
            {"name": "beta", "value": "beta"},
        ]

    def test_choices_with_dict(self) -> None:
        d = SelectPrompt(
            "Pick",
            choices=[{"name": "Alpha", "value": 1}, {"name": "Beta", "value": 2}],
        )._to_agent_dict()
        assert d["choices"] == [
            {"name": "Alpha", "value": 1},
            {"name": "Beta", "value": 2},
        ]


class TestCheckboxPromptFormat:
    def test_agent_dict_fields(self) -> None:
        d = CheckboxPrompt("Pick some", choices=["x", "y", "z"])._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "checkbox"
        assert d["message"] == "Pick some"
        assert "choices" in d
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_choices_structure(self) -> None:
        d = CheckboxPrompt("Pick", choices=["a", "b"])._to_agent_dict()
        assert d["choices"] == [
            {"name": "a", "value": "a"},
            {"name": "b", "value": "b"},
        ]


class TestNumberPromptFormat:
    def test_agent_dict_fields(self) -> None:
        d = NumberPrompt("Age?")._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "number"
        assert d["message"] == "Age?"
        assert d["default"] is None
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_type_specific_fields(self) -> None:
        d = NumberPrompt("N?", min=0, max=100, step=5, float_allowed=False)._to_agent_dict()
        assert d["min"] == 0
        assert d["max"] == 100
        assert d["num_step"] == 5
        assert d["float_allowed"] is False

    def test_type_specific_defaults(self) -> None:
        d = NumberPrompt("N?")._to_agent_dict()
        assert d["min"] is None
        assert d["max"] is None
        assert d["num_step"] is None
        assert d["float_allowed"] is True


class TestSearchPromptFormat:
    def test_agent_dict_fields(self) -> None:
        d = SearchPrompt("Search?", source=lambda term: ["foo", "bar"])._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "search"
        assert d["message"] == "Search?"
        assert "choices" in d
        assert d["searchable"] is True
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_initial_choices_populated(self) -> None:
        d = SearchPrompt("Search?", source=lambda term: ["apple", "banana"])._to_agent_dict()
        assert d["choices"] == [
            {"name": "apple", "value": "apple"},
            {"name": "banana", "value": "banana"},
        ]


class TestExpandPromptFormat:
    def test_agent_dict_fields(self) -> None:
        choices = [
            {"key": "o", "name": "Overwrite", "value": "overwrite"},
            {"key": "b", "name": "Backup", "value": "backup"},
        ]
        d = ExpandPrompt("Conflict?", choices=choices)._to_agent_dict()
        assert d["kind"] == "prompt"
        assert d["type"] == "expand"
        assert d["message"] == "Conflict?"
        assert "choices" in d
        assert PROMPT_REQUIRED_FIELDS.issubset(d.keys())

    def test_expand_choices_structure(self) -> None:
        choices = [
            ExpandChoice(key="o", name="Overwrite", value="overwrite"),
            ExpandChoice(key="b", name="Backup", value="backup"),
        ]
        d = ExpandPrompt("Conflict?", choices=choices)._to_agent_dict()
        assert d["choices"] == [
            {"key": "o", "name": "Overwrite", "value": "overwrite"},
            {"key": "b", "name": "Backup", "value": "backup"},
        ]


# ══════════════════════════════════════════════════════════════════════════════
# 3. Validation error format
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationErrorFormat:
    def test_validation_error_message_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When _validate_answer fails, the emitted JSON must have
        kind=validation_error and message=<str>."""
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        # First answer invalid, second valid
        _feed_stdin(monkeypatch, [{"answer": "not_a_choice"}, {"answer": "a"}])

        SelectPrompt("Pick", choices=["a", "b"]).execute()

        dicts = _collect_stdout_dicts(buf)
        errors = [d for d in dicts if d.get("kind") == "validation_error"]
        assert len(errors) >= 1
        err = errors[0]
        assert err["kind"] == "validation_error"
        assert "message" in err
        assert isinstance(err["message"], str)
        assert len(err["message"]) > 0

    def test_validation_error_from_number_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "abc"}, {"answer": 42}])

        NumberPrompt("N?").execute()

        dicts = _collect_stdout_dicts(buf)
        errors = [d for d in dicts if d.get("kind") == "validation_error"]
        assert len(errors) >= 1
        assert errors[0]["kind"] == "validation_error"
        assert isinstance(errors[0]["message"], str)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Answer extraction
# ══════════════════════════════════════════════════════════════════════════════


class TestAnswerExtraction:
    def test_string_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "hello"}])

        result = TextPrompt("Q?").execute()
        assert result == "hello"

    def test_bool_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": True}])

        result = ConfirmPrompt("Q?").execute()
        assert result is True

    def test_numeric_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": 42}])

        result = NumberPrompt("N?").execute()
        assert result == 42

    def test_list_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": ["a", "b"]}])

        result = CheckboxPrompt("Pick", choices=["a", "b", "c"]).execute()
        assert result == ["a", "b"]

    def test_null_answer_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": None}])

        result = TextPrompt("Q?", default="fallback").execute()
        assert result == "fallback"

    def test_malformed_json_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        monkeypatch.setattr("sys.stdin", io.StringIO("not valid json\n"))

        with pytest.raises(ValidationError, match="Invalid JSON"):
            TextPrompt("Q?").execute()

    def test_missing_answer_key_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"wrong_key": "x"}])

        with pytest.raises(ValidationError, match='"answer"'):
            TextPrompt("Q?").execute()

    def test_non_dict_json_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        monkeypatch.setattr("sys.stdin", io.StringIO('"just a string"\n'))

        with pytest.raises(ValidationError, match='"answer"'):
            TextPrompt("Q?").execute()

    def test_empty_stdin_raises_aborted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        _capture_stdout(monkeypatch)
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        with pytest.raises(PromptAbortedError):
            TextPrompt("Q?").execute()


# ══════════════════════════════════════════════════════════════════════════════
# 5. Retry invariant
# ══════════════════════════════════════════════════════════════════════════════


class TestRetryInvariant:
    def test_same_prompt_resent_after_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After a validation_error, the exact same prompt dict must be
        re-sent, not a new dict with different step or other fields."""
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        # First answer is invalid for select, second is valid
        _feed_stdin(monkeypatch, [{"answer": "nope"}, {"answer": "a"}])

        SelectPrompt("Pick", choices=["a", "b"]).execute()

        dicts = _collect_stdout_dicts(buf)
        prompts = _extract_prompts(dicts)
        assert len(prompts) == 2, f"Expected 2 prompt messages, got {len(prompts)}"
        assert prompts[0] == prompts[1], "After validation_error the re-sent prompt must be identical to the original"

    def test_retry_preserves_prompt_type_and_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _agent_env(monkeypatch)
        buf = _capture_stdout(monkeypatch)
        _feed_stdin(monkeypatch, [{"answer": "abc"}, {"answer": 10}])

        NumberPrompt("N?").execute()

        dicts = _collect_stdout_dicts(buf)
        prompts = _extract_prompts(dicts)
        assert len(prompts) == 2
        assert prompts[0]["type"] == prompts[1]["type"] == "number"
        assert prompts[0]["message"] == prompts[1]["message"] == "N?"
        assert prompts[0]["step"] == prompts[1]["step"]


# ══════════════════════════════════════════════════════════════════════════════
# 6. Property-based (hypothesis) tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPropertyBased:
    @given(
        message=st.text(min_size=1, max_size=200),
        default=st.one_of(st.none(), st.text(max_size=50)),
    )
    @settings(max_examples=200)
    def test_text_prompt_always_produces_valid_dict(self, message: str, default: str | None) -> None:
        d = TextPrompt(message, default=default)._to_agent_dict()
        # Must be JSON-serializable
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        # Required fields
        assert parsed["kind"] == "prompt"
        assert parsed["type"] == "input"
        assert parsed["message"] == message
        assert "default" in parsed
        assert "step" in parsed
        assert "total" in parsed

    @given(
        message=st.text(min_size=1, max_size=200),
        default=st.booleans(),
    )
    @settings(max_examples=200)
    def test_confirm_prompt_always_produces_valid_dict(self, message: str, default: bool) -> None:
        d = ConfirmPrompt(message, default=default)._to_agent_dict()
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        assert parsed["kind"] == "prompt"
        assert parsed["type"] == "confirm"
        assert parsed["message"] == message
        assert parsed["default"] is default

    @given(
        message=st.text(min_size=1, max_size=200),
        min_val=st.one_of(st.none(), st.integers(-1000, 1000)),
        max_val=st.one_of(st.none(), st.integers(-1000, 1000)),
    )
    @settings(max_examples=200)
    def test_number_prompt_always_produces_valid_dict(
        self, message: str, min_val: int | None, max_val: int | None
    ) -> None:
        d = NumberPrompt(message, min=min_val, max=max_val)._to_agent_dict()
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        assert parsed["kind"] == "prompt"
        assert parsed["type"] == "number"
        assert parsed["message"] == message
        assert "min" in parsed
        assert "max" in parsed
        assert "step" in parsed
        assert "float_allowed" in parsed

    @given(
        message=st.text(min_size=1, max_size=200),
        default=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False)),
    )
    @settings(max_examples=200)
    def test_agent_dict_always_json_serializable(self, message: str, default: float | None) -> None:
        """_to_agent_dict() must always produce valid JSON regardless of inputs."""
        d = NumberPrompt(message, default=default)._to_agent_dict()
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)
        for field in PROMPT_REQUIRED_FIELDS:
            assert field in parsed, f"Missing field: {field}"
