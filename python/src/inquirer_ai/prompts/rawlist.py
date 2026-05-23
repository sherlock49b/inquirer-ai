from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class RawlistPrompt(BasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice[Any]],
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        if not choices:
            raise ValueError("choices cannot be empty")
        self.choices: list[Choice[Any]] = [Choice.from_raw(c) for c in choices]  # pyright: ignore[reportUnknownMemberType]

    @property
    def prompt_type(self) -> str:
        return "rawlist"

    def _validate_answer(self, value: Any) -> Any:
        if isinstance(value, int) and 1 <= value <= len(self.choices):
            return self.choices[value - 1].value
        for c in self.choices:
            if value == c.value or value == c.name:
                return c.value
        raise ValidationError(f"Invalid choice: {value!r}")

    def _format_answer(self, value: Any) -> str:
        for c in self.choices:
            if c.value == value:
                return c.short or c.name
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [c.to_dict() for c in self.choices]
        return d

    def _execute_terminal(self) -> Any:
        t = get_theme()
        for i, c in enumerate(self.choices):
            print(f"  {i + 1}) {c.name}")
        while True:
            message = FormattedText(
                [
                    (t.pt(t.question), f"{t.sym_question} "),
                    ("bold", f"{self.message}: "),
                ]
            )
            raw = pt_prompt(message)
            try:
                idx = int(raw)
                if 1 <= idx <= len(self.choices):
                    return self.choices[idx - 1].value
            except ValueError:
                pass
            print(f"{t.ansi(t.error)}  Please enter a number between 1 and {len(self.choices)}{RESET}")
