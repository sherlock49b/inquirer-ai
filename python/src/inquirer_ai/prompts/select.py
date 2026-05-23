from __future__ import annotations

from typing import Any

from prompt_toolkit.key_binding import KeyBindings

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.choice_base import ChoiceBasePrompt
from inquirer_ai.theme import get_theme


class SelectPrompt(ChoiceBasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice[Any]],
        default: Any = None,
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, choices=choices, default=default, page_size=page_size, **kwargs)

    @property
    def prompt_type(self) -> str:
        return "select"

    def _validate_answer(self, value: Any) -> Any:
        for c in self.choices:
            if value == c.value or value == c.name:
                return c.value
        raise ValidationError(f"Invalid choice: {value!r}. Valid: {[c.value for c in self.choices]}")

    def _format_answer(self, value: Any) -> str:
        for c in self.choices:
            if c.value == value:
                return c.name
        return str(value)

    def _init_cursor(self) -> int:
        if self.default is not None:
            for i, c in enumerate(self.choices):
                if c.value == self.default or c.name == self.default:
                    return i
        return 0

    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice[Any]], state: dict[str, Any]) -> None:
        pass

    def _format_choice_line(self, index: int, choice: Choice[Any], state: dict[str, Any]) -> tuple[str, str]:
        t = get_theme()
        if index == state["cursor"]:
            return (t.pt_bold(t.highlight), f"{t.sym_pointer} {choice.name}")
        return ("", f"  {choice.name}")

    def _get_result(self, state: dict[str, Any]) -> Any:
        cursor: int = state["cursor"]
        return self.choices[cursor].value
