from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class ConfirmPrompt(BasePrompt):
    def __init__(self, message: str, *, default: bool = False) -> None:
        super().__init__(message, default=default)

    @property
    def prompt_type(self) -> str:
        return "confirm"

    def _validate_answer(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("y", "yes", "true", "1")
        return bool(value)

    def _execute_terminal(self) -> bool:
        t = get_theme()
        hint = "Y/n" if self.default else "y/N"
        message = FormattedText([
            (t.pt(t.question), "? "),
            ("bold", f"{self.message} ({hint}): "),
        ])
        while True:
            result = pt_prompt(message)
            if not result:
                answer = self.default  # type: ignore[assignment]
                break
            lower = result.strip().lower()
            if lower in ("y", "yes"):
                answer = True
                break
            if lower in ("n", "no"):
                answer = False
                break
            print(f"{t.ansi(t.error)}  Invalid input. Please enter y or n.{RESET}")
        label = "Yes" if answer else "No"
        print(f"{t.ansi(t.success)}✓{RESET} {self.message} {t.ansi(t.answer)}{label}{RESET}")
        return answer
