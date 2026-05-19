from __future__ import annotations

from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


class CheckboxPrompt(BasePrompt):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice],
        default: list[Any] | None = None,
    ) -> None:
        super().__init__(message, default=default or [])
        self.choices = [Choice.from_raw(c) for c in choices]

    @property
    def prompt_type(self) -> str:
        return "checkbox"

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [c.to_dict() for c in self.choices]
        return d

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

    def _execute_terminal(self) -> list[Any]:
        t = get_theme()
        cursor = 0
        choices = self.choices
        checked: set[int] = set()

        if self.default:
            for i, c in enumerate(choices):
                if c.value in self.default or c.name in self.default:
                    checked.add(i)

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event: Any) -> None:
            nonlocal cursor
            cursor = (cursor - 1) % len(choices)

        @kb.add("down")
        @kb.add("j")
        def _down(event: Any) -> None:
            nonlocal cursor
            cursor = (cursor + 1) % len(choices)

        @kb.add("space")
        def _toggle(event: Any) -> None:
            if cursor in checked:
                checked.discard(cursor)
            else:
                checked.add(cursor)

        @kb.add("a")
        def _toggle_all(event: Any) -> None:
            if len(checked) == len(choices):
                checked.clear()
            else:
                checked.update(range(len(choices)))

        @kb.add("enter")
        def _enter(event: Any) -> None:
            event.app.exit(result=[choices[i].value for i in sorted(checked)])

        @kb.add("c-c")
        def _abort(event: Any) -> None:
            event.app.exit(result=None)

        def get_message() -> FormattedText:
            return FormattedText([
                (t.pt(t.question), "? "),
                ("bold", self.message),
            ])

        def get_formatted_choices() -> FormattedText:
            lines: list[tuple[str, str]] = []
            for i, c in enumerate(choices):
                arrow = "❯" if i == cursor else " "
                mark = "◉" if i in checked else "◯"
                if i == cursor:
                    style = t.pt_bold(t.highlight)
                elif i in checked:
                    style = t.pt(t.selected)
                else:
                    style = ""
                lines.append((style, f"{arrow} {mark} {c.name}"))
                if i < len(choices) - 1:
                    lines.append(("", "\n"))
            return FormattedText(lines)

        layout = Layout(
            HSplit([
                Window(FormattedTextControl(get_message), height=1),
                Window(FormattedTextControl(get_formatted_choices)),
            ])
        )

        app: Application[Any] = Application(
            layout=layout, key_bindings=kb, full_screen=False, erase_when_done=True
        )
        result = app.run()
        if result is None:
            raise PromptAbortedError("Prompt aborted by user")
        names = [c.name for c in choices if c.value in result]
        summary = ", ".join(names) if names else "none"
        print(f"{t.ansi(t.success)}✓{RESET} {self.message} {t.ansi(t.answer)}{summary}{RESET}")
        return result
