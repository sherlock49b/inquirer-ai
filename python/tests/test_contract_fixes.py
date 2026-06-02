"""Tests locking in the review-fix contract behaviors (R2/R4/R5/R8)."""

from __future__ import annotations

import io
import json

import pytest

from inquirer_ai.choice import Choice, Separator, parse_choice, value_matches
from inquirer_ai.exceptions import InvalidChoiceError, ValidationError
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.expand import ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.password import PasswordPrompt
from inquirer_ai.prompts.rawlist import RawlistPrompt
from inquirer_ai.prompts.search import SearchPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.version import get_version

# ── R2: numeric-string grammar ──


class TestNumberGrammar:
    def _v(self, value, **kw):
        return NumberPrompt("q", **kw)._validate_answer(value)

    @pytest.mark.parametrize("bad", ["1_000", "3abc", "0x10", ".5", "5.", "", "+", "-", "1.2.3", " ", "abc"])
    def test_rejected_strings(self, bad):
        with pytest.raises(ValidationError, match="Not a valid number"):
            self._v(bad)

    def test_exponent_accepted(self):
        assert self._v("1e3") == 1000
        assert self._v("1E-3") == pytest.approx(0.001)

    def test_whitespace_trimmed(self):
        assert self._v("  5  ") == 5

    def test_fraction_and_sign(self):
        assert self._v("3.5") == pytest.approx(3.5)
        assert self._v("-2") == -2

    def test_integer_string_returns_int(self):
        r = self._v("42")
        assert r == 42 and isinstance(r, int)

    def test_float_string_returns_float(self):
        r = self._v("3.14")
        assert isinstance(r, float)

    def test_json_bool_is_not_a_number(self):
        with pytest.raises(ValidationError, match="Expected a number"):
            self._v(True)

    def test_other_type_message(self):
        with pytest.raises(ValidationError, match="Expected a number, got list"):
            self._v([1])

    def test_float_not_allowed_coerces_int(self):
        assert self._v(3.0, float_allowed=False) == 3
        with pytest.raises(ValidationError, match="Decimal numbers are not allowed"):
            self._v(3.5, float_allowed=False)

    def test_null_uses_default(self):
        assert NumberPrompt("q", default=7)._validate_answer(None) == 7


# ── R4: type-aware value matching ──


class TestValueMatches:
    def test_string_vs_number(self):
        assert not value_matches("42", 42)
        assert not value_matches(42, "42")

    def test_bool_vs_number(self):
        assert not value_matches(True, 1)
        assert not value_matches(1, True)
        assert not value_matches(False, 0)
        assert not value_matches(0, False)

    def test_same_type_value(self):
        assert value_matches(42, 42)
        assert value_matches("x", "x")
        assert value_matches(True, True)
        assert value_matches(1.5, 1.5)

    def test_int_float_cross_match(self):
        # Numbers compare by value across int/float (JSON has one number type).
        assert value_matches(1, 1.0)
        assert value_matches(2.0, 2)

    def test_none(self):
        assert value_matches(None, None)
        assert not value_matches(None, 0)


class TestSelectTypeAware:
    def test_zero_does_not_match_false(self):
        p = SelectPrompt("q", choices=[Choice(name="zero", value=0), Choice(name="f", value=False)])
        assert p._validate_answer(0) == 0
        assert p._validate_answer(False) is False

    def test_string_does_not_match_number_value(self):
        p = SelectPrompt("q", choices=[Choice(name="num", value=42)])
        with pytest.raises(ValidationError):
            p._validate_answer("42")

    def test_name_match_is_string_only(self):
        p = SelectPrompt("q", choices=[Choice(name="alpha", value=1)])
        assert p._validate_answer("alpha") == 1


class TestCheckboxTypeAware:
    def test_one_does_not_match_true(self):
        p = CheckboxPrompt("q", choices=[Choice(name="one", value=1), Choice(name="t", value=True)])
        assert p._validate_answer([1]) == [1]
        assert p._validate_answer([True]) == [True]


# ── R4: dict-form separators parsed everywhere ──


class TestDictSeparator:
    def test_parse_dict_separator(self):
        sep = parse_choice({"type": "separator", "text": "---"})
        assert isinstance(sep, Separator)
        assert sep.text == "---"

    def test_select_accepts_dict_separator(self):
        p = SelectPrompt("q", choices=["a", {"type": "separator"}, "b"])
        assert any(isinstance(i, Separator) for i in p.items)
        assert p._validate_answer("b") == "b"


# ── R4: expand non-string key ──


class TestExpandKey:
    def test_non_string_key_raises_invalid_choice(self):
        with pytest.raises(InvalidChoiceError, match="must be a string"):
            ExpandPrompt("q", choices=[{"key": 1, "name": "one"}])

    def test_keys_lowercased(self):
        p = ExpandPrompt("q", choices=[{"key": "Y", "name": "Yes", "value": "yes"}])
        assert p._validate_answer("y") == "yes"
        assert p.expand_choices[0].key == "y"


# ── R5: rawlist integer index + selectable filtering ──


class TestRawlistIndex:
    def test_bool_is_not_index(self):
        p = RawlistPrompt("q", choices=["a", "b"])
        with pytest.raises(ValidationError):
            p._validate_answer(True)

    def test_one_based_index(self):
        p = RawlistPrompt("q", choices=["a", "b", "c"])
        assert p._validate_answer(1) == "a"
        assert p._validate_answer(3) == "c"

    def test_index_out_of_range(self):
        p = RawlistPrompt("q", choices=["a"])
        with pytest.raises(ValidationError):
            p._validate_answer(2)

    def test_separators_and_disabled_excluded_from_indexing(self):
        p = RawlistPrompt(
            "q",
            choices=["a", {"type": "separator"}, Choice(name="d", value="d", disabled="no"), "b"],
        )
        # Selectable list is [a, b]; index 2 -> "b".
        assert p._validate_answer(2) == "b"
        assert [c.name for c in p.choices] == ["a", "b"]

    def test_payload_excludes_separators(self):
        p = RawlistPrompt("q", choices=["a", {"type": "separator"}, "b"])
        d = p._to_agent_dict()
        assert [c["name"] for c in d["choices"]] == ["a", "b"]
        assert "default" in d


# ── R5: search resolution ──


class TestSearchResolution:
    def test_match_resolves_to_value(self):
        p = SearchPrompt("q", source=lambda term: [Choice(name="Apple", value="apple")])
        assert p._validate_answer("apple") == "apple"
        assert p._validate_answer("Apple") == "apple"  # name match -> value

    def test_non_match_returns_verbatim(self):
        p = SearchPrompt("q", source=lambda term: [Choice(name="Apple", value="apple")])
        assert p._validate_answer("banana") == "banana"

    def test_socket_payload_has_resolved_choices(self):
        p = SearchPrompt("q", source=lambda term: ["x", "y"])
        d = p._to_agent_dict()
        assert d["searchable"] is True
        assert [c["name"] for c in d["choices"]] == ["x", "y"]


# ── R5: confirm/password null -> default ──


class TestConfirmDefault:
    def test_null_uses_default_true(self):
        assert ConfirmPrompt("q", default=True)._validate_answer(None) is True

    def test_null_uses_default_false(self):
        assert ConfirmPrompt("q", default=False)._validate_answer(None) is False

    def test_falsy_strings(self):
        p = ConfirmPrompt("q")
        for s in ("n", "no", "false", "0"):
            assert p._validate_answer(s) is False

    def test_truthy_strings(self):
        p = ConfirmPrompt("q")
        for s in ("y", "YES", "True", "1"):
            assert p._validate_answer(s) is True


class TestPasswordDefault:
    def test_null_uses_default(self):
        assert PasswordPrompt("q", default="secret")._validate_answer(None) == "secret"

    def test_null_no_default_is_empty(self):
        assert PasswordPrompt("q")._validate_answer(None) == ""

    def test_explicit_empty_string_verbatim(self):
        assert PasswordPrompt("q", default="x")._validate_answer("") == ""


# ── R8: version handshake ──


class TestVersion:
    def test_version_non_empty(self):
        assert isinstance(get_version(), str)
        assert get_version()

    def test_version_cached(self):
        # Cached: identical object returned on repeated calls.
        assert get_version() is get_version()

    def test_fallback_when_not_installed(self, monkeypatch):
        # An uninstalled source tree must fall back instead of raising (R8).
        import importlib.metadata as md

        import inquirer_ai.version as ver

        monkeypatch.setattr(ver, "_cached_version", None)

        def _raise(_name):
            raise md.PackageNotFoundError("inquirer-ai")

        monkeypatch.setattr(md, "version", _raise)
        try:
            assert ver.get_version() == "0.0.0"
        finally:
            ver._cached_version = None  # reset for other tests


# ── R1: unified stdio retry budget ──


class TestUnifiedStdioBudget:
    def _run(self, monkeypatch, prompt, stdin_text):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        hs = json.dumps({"kind": "handshake_ack"}) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(hs + stdin_text))
        out = io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        try:
            value = prompt.execute()
            err = None
        except BaseException as exc:
            value, err = None, exc
        kinds = [json.loads(line).get("kind") for line in out.getvalue().splitlines()]
        return value, err, kinds

    def test_two_validation_then_fatal_error(self, monkeypatch):
        # number coercion failure (bad numeric string) consumes the budget.
        bad = json.dumps({"answer": "abc"}) + "\n"
        p = NumberPrompt("q", validate=lambda v: True)
        _value, err, kinds = self._run(monkeypatch, p, bad * 3)
        assert isinstance(err, ValidationError)
        # 1 handshake + 3 prompts + 2 validation_error + 1 error
        assert kinds.count("validation_error") == 2
        assert kinds.count("error") == 1

    def test_coercion_and_user_validate_share_budget(self, monkeypatch):
        # One coercion failure + two user-validate failures = 3 total, ONE budget.
        bad_type = json.dumps({"answer": "abc"}) + "\n"
        too_small = json.dumps({"answer": 5}) + "\n"
        p = NumberPrompt("q", validate=lambda v: "too small" if v < 100 else True)
        _value, err, kinds = self._run(monkeypatch, p, bad_type + too_small + too_small)
        assert isinstance(err, ValidationError)
        assert kinds.count("validation_error") == 2
        assert kinds.count("error") == 1

    def test_recovery_within_budget(self, monkeypatch):
        p = NumberPrompt("q", validate=lambda v: "too small" if v < 100 else True)
        stdin = (
            json.dumps({"answer": "abc"}) + "\n" + json.dumps({"answer": 5}) + "\n" + json.dumps({"answer": 150}) + "\n"
        )
        value, err, kinds = self._run(monkeypatch, p, stdin)
        assert err is None
        assert value == 150
        assert kinds.count("validation_error") == 2
