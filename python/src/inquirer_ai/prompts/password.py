from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class PasswordPrompt(BasePrompt[str]):
    def __init__(self, message: str, *, mask: str | None = "*", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.mask = mask

    @property
    def prompt_type(self) -> str:
        return "password"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _format_answer(self, value: str) -> str:
        if self.mask:
            return self.mask * len(value)
        return "****"

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["mask"] = self.mask
        return d

    def _execute_terminal(self) -> str:
        t = get_theme()
        message = FormattedText(
            [
                (t.pt(t.question), f"{t.sym_question} "),
                ("bold", f"{self.message}: "),
            ]
        )
        return pt_prompt(message, is_password=True)
