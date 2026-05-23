"""Chaos and edge-case tests: malformed input, unicode bombs, boundary conditions."""

import io
import json

import pytest

from inquirer_ai.choice import Choice, Separator
from inquirer_ai.exceptions import InvalidChoiceError, PromptAbortedError, ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.expand import ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.password import PasswordPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

# Handshake ack line to prefix stdin so the handshake consumes it cleanly
_HS_ACK = json.dumps({"kind": "handshake_ack"}) + "\n"

# ── Malformed JSON in agent mode ──


class TestMalformedAgentInput:
    def _run(self, monkeypatch, prompt, stdin_text):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(_HS_ACK + stdin_text))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        return prompt.execute()

    def test_empty_stdin_raises_aborted(self, monkeypatch):
        with pytest.raises(PromptAbortedError, match="stdin closed"):
            self._run(monkeypatch, TextPrompt("q"), "")

    def test_garbage_json_raises_validation(self, monkeypatch):
        with pytest.raises(ValidationError, match="Invalid JSON"):
            self._run(monkeypatch, TextPrompt("q"), "not json\n")

    def test_json_array_instead_of_object(self, monkeypatch):
        with pytest.raises(ValidationError, match="answer"):
            self._run(monkeypatch, TextPrompt("q"), "[1, 2, 3]\n")

    def test_json_without_answer_key(self, monkeypatch):
        with pytest.raises(ValidationError, match="answer"):
            self._run(monkeypatch, TextPrompt("q"), '{"value": "hello"}\n')

    def test_json_null_top_level(self, monkeypatch):
        with pytest.raises(ValidationError, match="answer"):
            self._run(monkeypatch, TextPrompt("q"), "null\n")

    def test_json_number_top_level(self, monkeypatch):
        with pytest.raises(ValidationError, match="answer"):
            self._run(monkeypatch, TextPrompt("q"), "42\n")

    def test_json_string_top_level(self, monkeypatch):
        with pytest.raises(ValidationError, match="answer"):
            self._run(monkeypatch, TextPrompt("q"), '"hello"\n')


# ── Unicode edge cases ──


class TestUnicodeEdgeCases:
    def _agent_exec(self, monkeypatch, prompt, answer):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": answer}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        return prompt.execute()

    def test_emoji_in_text(self, monkeypatch):
        result = self._agent_exec(monkeypatch, TextPrompt("q"), "Hello 🌍🔥")
        assert result == "Hello 🌍🔥"

    def test_cjk_characters(self, monkeypatch):
        result = self._agent_exec(monkeypatch, TextPrompt("q"), "你好世界")
        assert result == "你好世界"

    def test_rtl_text(self, monkeypatch):
        result = self._agent_exec(monkeypatch, TextPrompt("q"), "مرحبا")
        assert result == "مرحبا"

    def test_zero_width_chars(self, monkeypatch):
        result = self._agent_exec(monkeypatch, TextPrompt("q"), "a​b‌c")
        assert result == "a​b‌c"

    def test_emoji_as_choice_name(self, monkeypatch):
        p = SelectPrompt("q", choices=["🍎", "🍌", "🍒"])
        result = self._agent_exec(monkeypatch, p, "🍌")
        assert result == "🍌"

    def test_newline_in_choice_name(self, monkeypatch):
        p = SelectPrompt("q", choices=["line1\nline2", "other"])
        result = self._agent_exec(monkeypatch, p, "line1\nline2")
        assert result == "line1\nline2"

    def test_empty_string_text(self, monkeypatch):
        result = self._agent_exec(monkeypatch, TextPrompt("q"), "")
        assert result == ""

    def test_very_long_string(self, monkeypatch):
        long_str = "x" * 100_000
        result = self._agent_exec(monkeypatch, TextPrompt("q"), long_str)
        assert result == long_str


# ── Boundary: choice configs ──


class TestChoiceBoundaries:
    def test_single_choice_select(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": "only"}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = SelectPrompt("q", choices=["only"])
        assert p.execute() == "only"

    def test_all_separators_raises(self):
        with pytest.raises(InvalidChoiceError, match="at least one selectable"):
            SelectPrompt("q", choices=[Separator(), Separator()])

    def test_mixed_disabled_separator_one_enabled(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": "ok"}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        choices = [
            Separator("---"),
            Choice("disabled1", "d1", disabled=True),
            "ok",
            Choice("disabled2", "d2", disabled="nope"),
            Separator(),
        ]
        p = SelectPrompt("q", choices=choices)
        assert p.execute() == "ok"
        assert p._init_cursor() == 2

    def test_default_on_disabled_choice_skips_to_first_enabled(self):
        choices = [
            Choice("disabled", "d", disabled=True),
            "enabled",
        ]
        p = SelectPrompt("q", choices=choices, default="d")
        assert p._init_cursor() == 1

    def test_checkbox_default_doesnt_check_disabled(self):
        choices = [
            Choice("a", "a", disabled=True),
            "b",
            "c",
        ]
        p = CheckboxPrompt("q", choices=choices, default=["a", "b"])
        assert 0 not in p._checked
        assert 1 in p._checked

    def test_select_agent_rejects_disabled_choice_value(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        # Provide 3 bad answers to exhaust retries
        lines = "".join(json.dumps({"answer": "d"}) + "\n" for _ in range(3))
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = SelectPrompt("q", choices=["a", Choice("Disabled", "d", disabled=True)])
        with pytest.raises(ValidationError):
            p.execute()

    def test_checkbox_agent_rejects_disabled_choice_value(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        # Provide 3 bad answers to exhaust retries
        lines = "".join(json.dumps({"answer": ["d"]}) + "\n" for _ in range(3))
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = CheckboxPrompt("q", choices=["a", Choice("Disabled", "d", disabled=True)])
        with pytest.raises(ValidationError):
            p.execute()


# ── Number edge cases ──


class TestNumberEdgeCases:
    def _agent_exec(self, monkeypatch, prompt, answer):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": answer}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        return prompt.execute()

    def _agent_exec_retry(self, monkeypatch, prompt, answer, retries=3):
        """Provide the same bad answer multiple times to exhaust retries."""
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = "".join(json.dumps({"answer": answer}) + "\n" for _ in range(retries))
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        return prompt.execute()

    def test_bool_true_rejected(self, monkeypatch):
        with pytest.raises(ValidationError, match="Expected a number"):
            self._agent_exec_retry(monkeypatch, NumberPrompt("q"), True)

    def test_bool_false_rejected(self, monkeypatch):
        with pytest.raises(ValidationError, match="Expected a number"):
            self._agent_exec_retry(monkeypatch, NumberPrompt("q"), False)

    def test_string_float(self, monkeypatch):
        result = self._agent_exec(monkeypatch, NumberPrompt("q"), "3.14")
        assert result == 3.14

    def test_string_negative(self, monkeypatch):
        result = self._agent_exec(monkeypatch, NumberPrompt("q"), "-42")
        assert result == -42

    def test_zero(self, monkeypatch):
        result = self._agent_exec(monkeypatch, NumberPrompt("q"), 0)
        assert result == 0

    def test_min_equals_max(self, monkeypatch):
        result = self._agent_exec(monkeypatch, NumberPrompt("q", min=5, max=5), 5)
        assert result == 5

    def test_min_equals_max_reject(self, monkeypatch):
        with pytest.raises(ValidationError):
            self._agent_exec_retry(monkeypatch, NumberPrompt("q", min=5, max=5), 4)

    def test_float_whole_number_converted_to_int(self, monkeypatch):
        result = self._agent_exec(monkeypatch, NumberPrompt("q", float_allowed=False), 7.0)
        assert result == 7
        assert isinstance(result, int)

    def test_none_without_default_raises(self, monkeypatch):
        with pytest.raises(ValidationError, match="Expected a number"):
            self._agent_exec_retry(monkeypatch, NumberPrompt("q"), None)


# ── Expand edge cases ──


class TestExpandEdgeCases:
    def test_case_insensitive_key(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": "Y"}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = ExpandPrompt("q", choices=[{"key": "y", "name": "Yes", "value": True}])
        assert p.execute() is True

    def test_answer_by_name(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": "Yes"}) + "\n"))
        monkeypatch.setattr("sys.stdout", io.StringIO())
        p = ExpandPrompt("q", choices=[{"key": "y", "name": "Yes", "value": "yes_val"}])
        assert p.execute() == "yes_val"


# ── Password: mask display ──


class TestPasswordDisplay:
    def test_mask_star_length_matches(self):
        p = PasswordPrompt("q", mask="*")
        assert p._format_answer("secret") == "******"
        assert p._format_answer("") == ""

    def test_mask_custom_char(self):
        p = PasswordPrompt("q", mask="•")
        assert p._format_answer("abc") == "•••"

    def test_no_mask_shows_generic(self):
        p = PasswordPrompt("q", mask=None)
        assert p._format_answer("anything") == "****"


# ── Cross-component: agent dict includes all fields ──


class TestAgentDictCompleteness:
    def test_select_includes_disabled_in_agent_dict(self):
        p = SelectPrompt("q", choices=["a", Choice("b", "b", disabled="not ready")])
        d = p._to_agent_dict()
        disabled_choice = [c for c in d["choices"] if c.get("disabled")]
        assert len(disabled_choice) == 1
        assert disabled_choice[0]["disabled"] == "not ready"

    def test_separator_in_agent_dict(self):
        p = SelectPrompt("q", choices=["a", Separator("---"), "b"])
        d = p._to_agent_dict()
        seps = [c for c in d["choices"] if c.get("type") == "separator"]
        assert len(seps) == 1
        assert seps[0]["text"] == "---"

    def test_choice_with_all_fields_in_agent_dict(self):
        c = Choice("PostgreSQL", "pg", short="PG", description="Relational DB")
        p = SelectPrompt("q", choices=[c])
        d = p._to_agent_dict()
        choice = d["choices"][0]
        assert choice["name"] == "PostgreSQL"
        assert choice["value"] == "pg"
        assert choice["short"] == "PG"
        assert choice["description"] == "Relational DB"


# ── Cursor navigation: tricky configurations ──


class TestCursorEdgeCases:
    def test_all_disabled_except_last(self):
        choices = [
            Choice("a", "a", disabled=True),
            Choice("b", "b", disabled=True),
            "c",
        ]
        p = SelectPrompt("q", choices=choices)
        assert p._init_cursor() == 2
        assert p._move_cursor(2, 1) == 2
        assert p._move_cursor(2, -1) == 2

    def test_separator_between_choices(self):
        choices = ["a", Separator(), "b"]
        p = SelectPrompt("q", choices=choices)
        assert p._move_cursor(0, 1) == 2
        assert p._move_cursor(2, -1) == 0

    def test_many_disabled_between_enabled(self):
        choices = [
            "start",
            Choice("d1", "d1", disabled=True),
            Choice("d2", "d2", disabled=True),
            Choice("d3", "d3", disabled=True),
            "end",
        ]
        p = SelectPrompt("q", choices=choices)
        assert p._move_cursor(0, 1) == 4
        assert p._move_cursor(4, -1) == 0

    def test_no_loop_stays_at_boundary(self):
        choices = ["a", "b", "c"]
        p = SelectPrompt("q", choices=choices, loop=False)
        assert p._move_cursor(2, 1) == 2
        assert p._move_cursor(0, -1) == 0

    def test_cursor_from_invalid_position_resets(self):
        choices = ["a", "b"]
        p = SelectPrompt("q", choices=choices)
        assert p._move_cursor(99, 1) == 0
