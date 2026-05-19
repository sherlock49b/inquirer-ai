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


class SelectPrompt(BasePrompt):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice],
        default: Any = None,
    ) -> None:
        super().__init__(message, default=default)
        self.choices = [Choice.from_raw(c) for c in choices]

    @property
    def prompt_type(self) -> str:
        return "select"

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [c.to_dict() for c in self.choices]
        return d

    def _validate_answer(self, value: Any) -> Any:
        for c in self.choices:
            if value == c.value or value == c.name:
                return c.value
        raise ValidationError(
            f"Invalid choice: {value!r}. "
            f"Valid: {[c.value for c in self.choices]}"
        )

    def _execute_terminal(self) -> Any:
        t = get_theme()
        cursor = 0
        choices = self.choices
        if self.default is not None:
            for i, c in enumerate(choices):
                if c.value == self.default or c.name == self.default:
                    cursor = i
                    break

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

        @kb.add("enter")
        def _enter(event: Any) -> None:
            event.app.exit(result=choices[cursor].value)

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
                if i == cursor:
                    lines.append((t.pt_bold(t.highlight), f"❯ {c.name}"))
                else:
                    lines.append(("", f"  {c.name}"))
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
        name = next(c.name for c in choices if c.value == result)
        print(f"{t.ansi(t.success)}✓{RESET} {self.message} {t.ansi(t.answer)}{name}{RESET}")
        return result
