"""Boundary condition tests: line endings, validator exceptions, invalid FDs, edge cases."""

import io
import json

import pytest

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import InvalidChoiceError, PromptAbortedError, ValidationError
from inquirer_ai.prompts.base import _get_agent_in, _get_agent_out
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

# Handshake ack line to prefix stdin so the handshake consumes it cleanly
_HS_ACK = json.dumps({"kind": "handshake_ack"}) + "\n"


class TestCRLFLineEndings:
    """Fix 1: \\r\\n line endings should be stripped in agent mode."""

    def test_crlf_answer_parsed(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        # Simulate Windows-style line ending: JSON followed by \r\n
        stdin_text = _HS_ACK + '{"answer": "hello"}\r\n'
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        result = TextPrompt("q").execute()
        assert result == "hello"


class TestValidatorExceptions:
    """Fix 2: Non-ValidationError exceptions from validators should be caught."""

    def _run(self, monkeypatch, validate_fn):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(_HS_ACK + '{"answer": "x"}\n'))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = TextPrompt("q", validate=validate_fn)
        return p.execute()

    def test_type_error_converted(self, monkeypatch):
        def bad_validator(v):
            raise TypeError("expected int, got str")

        with pytest.raises(ValidationError, match="expected int, got str"):
            self._run(monkeypatch, bad_validator)

    def test_runtime_error_converted(self, monkeypatch):
        def bad_validator(v):
            raise RuntimeError("connection lost")

        with pytest.raises(ValidationError, match="connection lost"):
            self._run(monkeypatch, bad_validator)

    def test_validation_error_passes_through(self, monkeypatch):
        def validator(v):
            raise ValidationError("custom validation error")

        with pytest.raises(ValidationError, match="custom validation error"):
            self._run(monkeypatch, validator)


class TestInvalidFDEnvVars:
    """Fix 3: Invalid INQUIRER_AI_FD_OUT/FD_IN env vars should fall back gracefully."""

    def test_non_numeric_fd_out_falls_back(self, monkeypatch, capsys):
        monkeypatch.setenv("INQUIRER_AI_FD_OUT", "not_a_number")
        import sys

        result = _get_agent_out()
        assert result is sys.stdout
        captured = capsys.readouterr()
        assert "INQUIRER_AI_FD_OUT" in captured.err
        assert "falling back" in captured.err

    def test_non_numeric_fd_in_falls_back(self, monkeypatch, capsys):
        monkeypatch.setenv("INQUIRER_AI_FD_IN", "garbage")
        import sys

        result = _get_agent_in()
        assert result is sys.stdin
        captured = capsys.readouterr()
        assert "INQUIRER_AI_FD_IN" in captured.err
        assert "falling back" in captured.err

    def test_invalid_fd_number_out_falls_back(self, monkeypatch, capsys):
        # Use an FD number that is almost certainly not open
        monkeypatch.setenv("INQUIRER_AI_FD_OUT", "9999")
        import sys

        result = _get_agent_out()
        assert result is sys.stdout
        captured = capsys.readouterr()
        assert "INQUIRER_AI_FD_OUT" in captured.err

    def test_invalid_fd_number_in_falls_back(self, monkeypatch, capsys):
        monkeypatch.setenv("INQUIRER_AI_FD_IN", "9999")
        import sys

        result = _get_agent_in()
        assert result is sys.stdin
        captured = capsys.readouterr()
        assert "INQUIRER_AI_FD_IN" in captured.err


class TestAllChoicesDisabled:
    """Empty or all-disabled choice lists should raise InvalidChoiceError."""

    def test_all_choices_disabled(self):
        with pytest.raises(InvalidChoiceError, match="at least one selectable"):
            SelectPrompt(
                "q",
                choices=[
                    Choice("a", "a", disabled=True),
                    Choice("b", "b", disabled=True),
                ],
            )

    def test_empty_choice_list(self):
        with pytest.raises(InvalidChoiceError, match="cannot be empty"):
            SelectPrompt("q", choices=[])

    def test_checkbox_empty_choices(self):
        with pytest.raises(InvalidChoiceError, match="cannot be empty"):
            CheckboxPrompt("q", choices=[])

    def test_checkbox_all_disabled(self):
        with pytest.raises(InvalidChoiceError, match="at least one selectable"):
            CheckboxPrompt(
                "q",
                choices=[
                    Choice("x", "x", disabled=True),
                    Choice("y", "y", disabled="nope"),
                ],
            )


class TestStdinEOFAgentMode:
    """stdin EOF in agent mode should raise PromptAbortedError."""

    def test_eof_raises_aborted(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        # Empty stdin after handshake ack -> EOF
        monkeypatch.setattr("sys.stdin", io.StringIO(_HS_ACK))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        with pytest.raises(PromptAbortedError, match="stdin closed"):
            TextPrompt("q").execute()
