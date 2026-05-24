from __future__ import annotations

import math
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class ConfirmPrompt(BasePrompt[bool]):
    def __init__(self, message: str, *, default: bool = False, **kwargs: Any) -> None:
        super().__init__(message, default=default, **kwargs)

    @property
    def prompt_type(self) -> str:
        return "confirm"

    def _validate_answer(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("y", "yes", "true", "1")
        if isinstance(value, float) and not math.isfinite(value):
            return False
        return bool(value)

    def _format_answer(self, value: bool) -> str:
        return "Yes" if value else "No"

    def _execute_terminal(self) -> bool:
        t = get_theme()
        hint = "Y/n" if self.default else "y/N"
        message = FormattedText(
            [
                (t.pt(t.question), f"{t.sym_question} "),
                ("bold", f"{self.message} ({hint}): "),
            ]
        )
        while True:
            result = pt_prompt(message)
            if not result:
                return self.default
            lower = result.strip().lower()
            if lower in ("y", "yes"):
                return True
            if lower in ("n", "no"):
                return False
            print(f"{t.ansi(t.error)}  Invalid input. Please enter y or n.{RESET}")
