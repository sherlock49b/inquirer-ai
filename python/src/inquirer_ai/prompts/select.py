from __future__ import annotations

from typing import Any

from prompt_toolkit.key_binding import KeyBindings

from inquirer_ai.choice import Choice, ChoiceItem, RawChoice, Separator
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.choice_base import ChoiceBasePrompt, PromptState
from inquirer_ai.theme import get_theme


class SelectPrompt(ChoiceBasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[RawChoice],
        default: Any = None,
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, choices=choices, default=default, page_size=page_size, **kwargs)

    @property
    def prompt_type(self) -> str:
        return "select"

    def _validate_answer(self, value: Any) -> Any:
        valid: list[Any] = []
        for c in self.choices:
            if c.disabled:
                continue
            if value == c.value or value == c.name:
                return c.value
            valid.append(c.value)
        raise ValidationError(f"Invalid choice: {value!r}. Valid: {valid}")

    def _format_answer(self, value: Any) -> str:
        for c in self.choices:
            if c.value == value:
                return c.short or c.name
        return str(value)

    def _init_cursor(self) -> int:
        if self.default is not None:
            for i, item in enumerate(self.items):
                if (
                    isinstance(item, Choice)
                    and not item.disabled
                    and (item.value == self.default or item.name == self.default)
                ):
                    return i
        return self._selectable_indices()[0]

    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice[Any]], state: PromptState) -> None:
        pass

    def _format_choice_line(self, index: int, item: ChoiceItem, state: PromptState) -> tuple[str, str]:
        t = get_theme()
        if isinstance(item, Separator):
            return (t.pt(t.muted), f"  {item.text}")
        if item.disabled:
            reason = f" ({item.disabled})" if isinstance(item.disabled, str) else ""
            return (t.pt(t.muted), f"  {item.name}{reason} (disabled)")
        if index == state["cursor"]:
            desc = f" - {item.description}" if item.description else ""
            return (t.pt_bold(t.highlight), f"{t.sym_pointer} {item.name}{desc}")
        return ("", f"  {item.name}")

    def _get_result(self, state: PromptState) -> Any:
        cursor: int = state["cursor"]
        item = self.items[cursor]
        assert isinstance(item, Choice)
        return item.value
