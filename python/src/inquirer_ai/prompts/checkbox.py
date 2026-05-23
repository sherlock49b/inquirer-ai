from __future__ import annotations

from typing import Any

from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.choice_base import ChoiceBasePrompt
from inquirer_ai.theme import get_theme


class CheckboxPrompt(ChoiceBasePrompt[list[Any]]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice[Any]],
        default: list[Any] | None = None,
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, choices=choices, default=default or [], page_size=page_size, **kwargs)
        self._checked: set[int] = set()
        if self.default:
            for i, c in enumerate(self.choices):
                if c.value in self.default or c.name in self.default:
                    self._checked.add(i)

    @property
    def prompt_type(self) -> str:
        return "checkbox"

    def _validate_answer(self, value: Any) -> list[Any]:
        if not isinstance(value, list):
            raise ValidationError(f"Expected a list, got {type(value).__name__}")
        result = []
        valid_values = {c.value for c in self.choices}
        valid_names = {c.name for c in self.choices}
        for v in value:
            if v in valid_values:
                result.append(v)
            elif v in valid_names:
                for c in self.choices:
                    if c.name == v:
                        result.append(c.value)
                        break
            else:
                raise ValidationError(
                    f"Invalid choice: {v!r}. Valid: {list(valid_values)}"
                )
        return result

    def _format_answer(self, value: list[Any]) -> str:
        names = [c.name for c in self.choices if c.value in value]
        return ", ".join(names) if names else "none"

    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice[Any]], state: dict[str, Any]) -> None:
        checked = self._checked

        @kb.add("space")
        def _toggle(event: KeyPressEvent) -> None:
            cursor = state["cursor"]
            if cursor in checked:
                checked.discard(cursor)
            else:
                checked.add(cursor)

        @kb.add("a")
        def _toggle_all(event: KeyPressEvent) -> None:
            if len(checked) == len(choices):
                checked.clear()
            else:
                checked.update(range(len(choices)))

    def _format_choice_line(self, index: int, choice: Choice[Any], state: dict[str, Any]) -> tuple[str, str]:
        t = get_theme()
        arrow = t.sym_pointer if index == state["cursor"] else " "
        mark = t.sym_checked if index in self._checked else t.sym_unchecked
        if index == state["cursor"]:
            style = t.pt_bold(t.highlight)
        elif index in self._checked:
            style = t.pt(t.selected)
        else:
            style = ""
        return (style, f"{arrow} {mark} {choice.name}")

    def _get_result(self, state: dict[str, Any]) -> list[Any]:
        return [self.choices[i].value for i in sorted(self._checked)]
