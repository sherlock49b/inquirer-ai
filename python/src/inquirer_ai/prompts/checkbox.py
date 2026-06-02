from __future__ import annotations

import json
from typing import Any, TypeGuard

from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from inquirer_ai.choice import Choice, ChoiceItem, RawChoice, Separator, value_matches
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.choice_base import ChoiceBasePrompt, PromptState
from inquirer_ai.theme import get_theme


class CheckboxPrompt(ChoiceBasePrompt[list[Any]]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[RawChoice],
        default: list[Any] | None = None,
        required: bool | str = False,
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, choices=choices, default=default or [], page_size=page_size, **kwargs)
        self.required = required
        self._checked: set[int] = set()
        if self.default:
            for i, item in enumerate(self.items):
                if (
                    isinstance(item, Choice)
                    and not item.disabled
                    and (
                        any(value_matches(d, item.value) for d in self.default)
                        or any(isinstance(d, str) and d == item.name for d in self.default)
                    )
                ):
                    self._checked.add(i)

    @property
    def prompt_type(self) -> str:
        return "checkbox"

    @staticmethod
    def _is_list(value: object) -> TypeGuard[list[Any]]:
        return isinstance(value, list)

    def _validate_answer(self, value: Any) -> list[Any]:
        if not self._is_list(value):
            raise ValidationError(f"Expected a list, got {type(value).__name__}")
        input_items = value
        result: list[Any] = []
        enabled = [c for c in self.choices if not c.disabled]
        valid_values: list[Any] = [c.value for c in enabled]
        for v in input_items:
            matched = False
            for c in enabled:
                if value_matches(v, c.value) or (isinstance(v, str) and v == c.name):
                    result.append(c.value)
                    matched = True
                    break
            if not matched:
                valid_repr = ", ".join(json.dumps(val) for val in valid_values)
                raise ValidationError(f"Invalid choice: {json.dumps(v)}. Valid: [{valid_repr}]")
        if self.required and not result:
            msg = self.required if isinstance(self.required, str) else "At least one choice is required"
            raise ValidationError(msg)
        return result

    def _format_answer(self, value: list[Any]) -> str:
        names = [c.short or c.name for c in self.choices if c.value in value]
        return ", ".join(names) if names else "none"

    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice[Any]], state: PromptState) -> None:
        checked = self._checked
        selectable = self._selectable_indices()

        @kb.add("space")
        def _toggle(event: KeyPressEvent) -> None:
            cursor = state["cursor"]
            if self._is_selectable(cursor):
                if cursor in checked:
                    checked.discard(cursor)
                else:
                    checked.add(cursor)

        @kb.add("a")
        def _toggle_all(event: KeyPressEvent) -> None:
            if len(checked) == len(selectable):
                checked.clear()
            else:
                checked.update(selectable)

    def _format_choice_line(self, index: int, item: ChoiceItem, state: PromptState) -> tuple[str, str]:
        t = get_theme()
        if isinstance(item, Separator):
            return (t.pt(t.muted), f"  {item.text}")
        if item.disabled:
            reason = f" ({item.disabled})" if isinstance(item.disabled, str) else ""
            return (t.pt(t.muted), f"  {t.sym_unchecked} {item.name}{reason} (disabled)")
        arrow = t.sym_pointer if index == state["cursor"] else " "
        mark = t.sym_checked if index in self._checked else t.sym_unchecked
        if index == state["cursor"]:
            style = t.pt_bold(t.highlight)
        elif index in self._checked:
            style = t.pt(t.selected)
        else:
            style = ""
        return (style, f"{arrow} {mark} {item.name}")

    def _get_result(self, state: PromptState) -> list[Any]:
        result: list[Any] = []
        for i in sorted(self._checked):
            item = self.items[i]
            if isinstance(item, Choice):
                result.append(item.value)
        return result
