from __future__ import annotations

from abc import abstractmethod
from typing import Any, TypeVar

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window

from inquirer_ai.choice import Choice
from inquirer_ai.exceptions import PromptAbortedError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme

T = TypeVar("T")


class ChoiceBasePrompt(BasePrompt[T]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[str | dict[str, Any] | Choice],
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        if not choices:
            raise ValueError("choices cannot be empty")
        self.choices = [Choice.from_raw(c) for c in choices]
        self.page_size = page_size

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [c.to_dict() for c in self.choices]
        return d

    @abstractmethod
    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice], state: dict[str, Any]) -> None: ...

    @abstractmethod
    def _format_choice_line(self, index: int, choice: Choice, state: dict[str, Any]) -> tuple[str, str]: ...

    @abstractmethod
    def _get_result(self, state: dict[str, Any]) -> Any: ...

    def _init_cursor(self) -> int:
        return 0

    def _execute_terminal(self) -> T:
        t = get_theme()
        choices = self.choices
        state: dict[str, Any] = {"cursor": self._init_cursor()}

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event: KeyPressEvent) -> None:
            state["cursor"] = (state["cursor"] - 1) % len(choices)

        @kb.add("down")
        @kb.add("j")
        def _down(event: KeyPressEvent) -> None:
            state["cursor"] = (state["cursor"] + 1) % len(choices)

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            event.app.exit(result=self._get_result(state))

        @kb.add("c-c")
        def _abort(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        self._build_keybindings(kb, choices, state)

        def get_message() -> FormattedText:
            return FormattedText([
                (t.pt(t.question), "? "),
                ("bold", self.message),
            ])

        def _visible_range() -> tuple[int, int]:
            cursor = state["cursor"]
            total = len(choices)
            ps = min(self.page_size, total)
            start = max(0, min(cursor - ps // 2, total - ps))
            return start, start + ps

        def get_formatted_choices() -> FormattedText:
            lines: list[tuple[str, str]] = []
            start, end = _visible_range()
            if start > 0:
                lines.append((t.pt(t.muted), "  (more above)"))
                lines.append(("", "\n"))
            for i in range(start, end):
                lines.append(self._format_choice_line(i, choices[i], state))
                if i < end - 1:
                    lines.append(("", "\n"))
            if end < len(choices):
                lines.append(("", "\n"))
                lines.append((t.pt(t.muted), "  (more below)"))
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
        return result
