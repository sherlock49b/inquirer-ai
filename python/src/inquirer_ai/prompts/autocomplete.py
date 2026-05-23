from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class AutocompletePrompt(BasePrompt[str]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.choices = choices

    @property
    def prompt_type(self) -> str:
        return "autocomplete"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = self.choices
        return d

    def _execute_terminal(self) -> str:
        t = get_theme()
        suffix = f" ({self.default})" if self.default is not None else ""
        message = FormattedText(
            [
                (t.pt(t.question), f"{t.sym_question} "),
                ("bold", f"{self.message}{suffix}: "),
            ]
        )
        completer = WordCompleter(self.choices, ignore_case=True)
        result = pt_prompt(message, completer=completer)
        if not result and self.default is not None:
            result = self.default
        return result
