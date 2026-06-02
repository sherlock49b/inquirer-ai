from __future__ import annotations

import math
import re
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme

# Numeric-string grammar (R2): optional sign; required integer part; optional
# .fraction; optional exponent. Rejects "1_000", "3abc", "0x10", ".5", "5.",
# "", "+". Accepts "1e3", "3.5", "-2", "1E-3".
_NUMBER_RE = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")
# ASCII whitespace to strip (leading/trailing) before matching.
_ASCII_WS = " \t\n\r\f\v"


class NumberPrompt(BasePrompt[int | float]):
    def __init__(
        self,
        message: str,
        *,
        min: int | float | None = None,
        max: int | float | None = None,
        step: int | float | None = None,
        float_allowed: bool = True,
        keep_input: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.min = min
        self.max = max
        self.step = step
        self.float_allowed = float_allowed
        self.keep_input = keep_input

    @property
    def prompt_type(self) -> str:
        return "number"

    def _validate_answer(self, value: Any) -> int | float:
        # 1) null + default present -> default.
        if value is None and self.default is not None:
            return self.default
        num: int | float
        if isinstance(value, bool):
            # 4) bool is not a number.
            raise ValidationError(f"Expected a number, got {type(value).__name__}")
        elif isinstance(value, (int, float)):
            # 2) JSON number (not boolean) -> use it.
            num = value
        elif isinstance(value, str):
            # 3) trim leading/trailing ASCII whitespace then enforce the grammar.
            trimmed = value.strip(_ASCII_WS)
            if not _NUMBER_RE.match(trimmed):
                raise ValidationError(f"Not a valid number: {value!r}")
            # Parse with the native float parser; return an int (language-idiomatic)
            # for pure-integer forms (no fraction/exponent). Numeric value is
            # identical across languages either way.
            num = float(trimmed) if any(ch in trimmed for ch in ".eE") else int(trimmed)
        else:
            # 4) other type.
            raise ValidationError(f"Expected a number, got {type(value).__name__}")
        # 5) reject non-finite (NaN/Inf).
        if isinstance(num, float) and not math.isfinite(num):
            raise ValidationError(f"Not a valid number: {value!r}")
        # 6) if !float_allowed: require integral else error, then coerce to int.
        if not self.float_allowed:
            if isinstance(num, float) and not num.is_integer():
                raise ValidationError("Decimal numbers are not allowed")
            num = int(num)
        if self.min is not None and num < self.min:
            raise ValidationError(f"Must be at least {self.min}")
        if self.max is not None and num > self.max:
            raise ValidationError(f"Must be at most {self.max}")
        if self.step is not None:
            base = self.min if self.min is not None else 0
            remainder = (num - base) % self.step
            if abs(remainder) > 1e-9 and abs(remainder - self.step) > 1e-9:
                raise ValidationError(f"Must be a multiple of {self.step} (from {base})")
        return num

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["min"] = self.min
        d["max"] = self.max
        d["num_step"] = self.step
        d["float_allowed"] = self.float_allowed
        return d

    def _execute_terminal(self) -> int | float:
        t = get_theme()
        suffix = f" ({self.default})" if self.default is not None else ""
        retry_default: str | None = None
        while True:
            message = FormattedText(
                [
                    (t.pt(t.question), f"{t.sym_question} "),
                    ("bold", f"{self.message}{suffix}: "),
                ]
            )
            raw = pt_prompt(message, default=retry_default or "")
            if not raw and self.default is not None:
                return self.default
            try:
                result = self._validate_answer(raw)
            except ValidationError as e:
                print(f"{t.ansi(t.error)}  {e}{RESET}")
                retry_default = raw if self.keep_input else None
                continue
            # Run user-provided validation
            error = self._run_user_validation(result)
            if error:
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                retry_default = raw if self.keep_input else None
                continue
            return result
