from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class TextPrompt(BasePrompt[str]):
    def __init__(
        self,
        message: str,
        *,
        keep_input: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.keep_input = keep_input

    @property
    def prompt_type(self) -> str:
        return "input"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _execute_terminal(self) -> str:
        from inquirer_ai.theme import RESET

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
            result = pt_prompt(message, default=retry_default or "")
            if not result and self.default is not None:
                result = self.default
            # Run user-provided validation in terminal loop
            error = self._run_user_validation(result)
            if error:
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                retry_default = result if self.keep_input else None
                continue
            return result
