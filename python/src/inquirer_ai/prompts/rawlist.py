from __future__ import annotations

import json
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.choice import Choice, RawChoice, parse_choice, value_matches
from inquirer_ai.exceptions import InvalidChoiceError, ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class RawlistPrompt(BasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[RawChoice],
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        if not choices:
            raise InvalidChoiceError("choices cannot be empty")
        # The selectable list excludes separators AND disabled choices (R5).
        # Indexing (1..n) and matching operate over this list only.
        parsed = [parse_choice(c) for c in choices]
        self.choices: list[Choice[Any]] = [c for c in parsed if isinstance(c, Choice) and not c.disabled]
        if not self.choices:
            raise InvalidChoiceError("choices must contain at least one selectable item")

    @property
    def prompt_type(self) -> str:
        return "rawlist"

    def _validate_answer(self, value: Any) -> Any:
        # A 1-based integer index (but NOT a bool — JSON true/false is not an index).
        if isinstance(value, int) and not isinstance(value, bool):
            if 1 <= value <= len(self.choices):
                return self.choices[value - 1].value
            raise ValidationError(self._invalid_choice_message(value))
        for c in self.choices:
            if value_matches(value, c.value) or (isinstance(value, str) and value == c.name):
                return c.value
        raise ValidationError(self._invalid_choice_message(value))

    def _invalid_choice_message(self, value: Any) -> str:
        valid_repr = ", ".join(json.dumps(c.value) for c in self.choices)
        return f"Invalid choice: {json.dumps(value)}. Valid: [{valid_repr}]"

    def _format_answer(self, value: Any) -> str:
        for c in self.choices:
            if c.value == value:
                return c.short or c.name
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        # Payload "choices" excludes separators + disabled, numbered 1..n (R5/R6).
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
