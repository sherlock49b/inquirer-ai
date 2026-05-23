from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import BufferControl, FormattedTextControl, HSplit, Layout, Window

from inquirer_ai.choice import Choice, RawChoice, parse_choice
from inquirer_ai.exceptions import PromptAbortedError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class SearchPrompt(BasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        source: Callable[[str], list[RawChoice]],
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.source = source
        self.page_size = page_size

    @property
    def prompt_type(self) -> str:
        return "search"

    def _validate_answer(self, value: Any) -> Any:
        return value

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["searchable"] = True
        initial: list[Choice[Any]] = [c for raw in self.source("") if isinstance((c := parse_choice(raw)), Choice)]
        d["choices"] = [c.to_dict() for c in initial]
        return d

    def _execute_terminal(self) -> Any:
        t = get_theme()
        state: dict[str, Any] = {"cursor": 0, "filtered": []}
        self._update_filtered(state, "")

        search_buffer = Buffer(
            on_text_changed=lambda buf: self._update_filtered(state, buf.text),
        )

        kb = KeyBindings()

        @kb.add("up")
        def _up(event: KeyPressEvent) -> None:
            if state["filtered"]:
                state["cursor"] = (state["cursor"] - 1) % len(state["filtered"])

        @kb.add("down")
        def _down(event: KeyPressEvent) -> None:
            if state["filtered"]:
                state["cursor"] = (state["cursor"] + 1) % len(state["filtered"])

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            filtered: list[Choice[Any]] = state["filtered"]
            if filtered:
                event.app.exit(result=filtered[state["cursor"]].value)  # pyright: ignore[reportUnknownMemberType]
            else:
                event.app.exit(result=None)

        @kb.add("c-c")
        def _abort(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        def get_message() -> FormattedText:
            return FormattedText(
                [
                    (t.pt(t.question), f"{t.sym_question} "),
                    ("bold", f"{self.message}: "),
                ]
            )

        def get_choices() -> FormattedText:
            filtered: list[Choice[Any]] = state["filtered"]
            lines: list[tuple[str, str]] = []
            end = min(len(filtered), self.page_size)
            for i in range(end):
                choice = filtered[i]
                if i == state["cursor"]:
                    lines.append((t.pt_bold(t.highlight), f"{t.sym_pointer} {choice.name}"))
                else:
                    lines.append(("", f"  {choice.name}"))
                if i < end - 1:
                    lines.append(("", "\n"))
            if not filtered:
                lines.append((t.pt(t.muted), "  No matches"))
            return FormattedText(lines)

        layout = Layout(
            HSplit(
                [
                    Window(FormattedTextControl(get_message), height=1),
                    Window(BufferControl(buffer=search_buffer), height=1),
                    Window(FormattedTextControl(get_choices)),
                ]
            )
        )

        app: Application[Any] = Application(layout=layout, key_bindings=kb, full_screen=False, erase_when_done=True)
        result = app.run()
        if result is None:
            raise PromptAbortedError("Prompt aborted by user")
        return result

    def _update_filtered(self, state: dict[str, Any], term: str) -> None:
        raw_choices = self.source(term)
        state["filtered"] = [
            c for raw in raw_choices if isinstance((c := parse_choice(raw)), Choice) and not c.disabled
        ]
        state["cursor"] = 0
