from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class TextPrompt(BasePrompt[str]):
    @property
    def prompt_type(self) -> str:
        return "input"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _execute_terminal(self) -> str:
        t = get_theme()
        suffix = f" ({self.default})" if self.default is not None else ""
        message = FormattedText([
            (t.pt(t.question), "? "),
            ("bold", f"{self.message}{suffix}: "),
        ])
        result = pt_prompt(message)
        if not result and self.default is not None:
            result = self.default
        return result
