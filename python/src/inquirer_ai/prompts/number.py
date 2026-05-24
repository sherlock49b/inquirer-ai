from __future__ import annotations

import math
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class NumberPrompt(BasePrompt[int | float]):
    def __init__(
        self,
        message: str,
        *,
        min: int | float | None = None,
        max: int | float | None = None,
        float_allowed: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.min = min
        self.max = max
        self.float_allowed = float_allowed

    @property
    def prompt_type(self) -> str:
        return "number"

    def _validate_answer(self, value: Any) -> int | float:
        if value is None and self.default is not None:
            return self.default
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValidationError(f"Not a valid number: {value}")
            num = value
        elif isinstance(value, str):
            try:
                num = float(value) if "." in value else int(value)
            except ValueError:
                raise ValidationError(f"Not a valid number: {value!r}") from None
            if isinstance(num, float) and not math.isfinite(num):
                raise ValidationError(f"Not a valid number: {value!r}")
        else:
            raise ValidationError(f"Expected a number, got {type(value).__name__}")
        if not self.float_allowed and isinstance(num, float):
            if num != int(num):  # pyright: ignore[reportUnnecessaryComparison]
                raise ValidationError("Decimal numbers are not allowed")
            num = int(num)
        if self.min is not None and num < self.min:
            raise ValidationError(f"Must be at least {self.min}")
        if self.max is not None and num > self.max:
            raise ValidationError(f"Must be at most {self.max}")
        return num

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["min"] = self.min
        d["max"] = self.max
        d["float_allowed"] = self.float_allowed
        return d

    def _execute_terminal(self) -> int | float:
        t = get_theme()
        suffix = f" ({self.default})" if self.default is not None else ""
        message = FormattedText(
            [
                (t.pt(t.question), f"{t.sym_question} "),
                ("bold", f"{self.message}{suffix}: "),
            ]
        )
        while True:
            raw = pt_prompt(message)
            if not raw and self.default is not None:
                return self.default
            try:
                return self._validate_answer(raw)
            except ValidationError as e:
                print(f"{t.ansi(t.error)}  {e}{RESET}")
