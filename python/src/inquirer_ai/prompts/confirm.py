from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt

from inquirer_ai.prompts.base import BasePrompt


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
        hint = "Y/n" if self.default else "y/N"
        result = pt_prompt(f"? {self.message} ({hint}): ")
        if not result:
            return self.default  # type: ignore[return-value]
        return result.strip().lower() in ("y", "yes")
