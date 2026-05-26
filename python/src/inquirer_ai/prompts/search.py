from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
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
        source: Callable[[str], list[RawChoice]] | Callable[[str], Awaitable[list[RawChoice]]],
        page_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.source = source
        self.page_size = page_size
        self._is_async_source = inspect.iscoroutinefunction(source)

    def _call_source_sync(self, term: str) -> list[RawChoice]:
        """Call source synchronously. If source is async, run it in a new event loop."""
        if self._is_async_source:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self.source(term)).result()  # type: ignore[arg-type]
            return asyncio.run(self.source(term))  # type: ignore[arg-type]
        return self.source(term)  # type: ignore[return-value]

    async def _call_source_async(self, term: str) -> list[RawChoice]:
        """Call source asynchronously. If source is sync, call it directly."""
        if self._is_async_source:
            return await self.source(term)  # type: ignore[misc]
        return self.source(term)  # type: ignore[return-value]

    @property
    def prompt_type(self) -> str:
        return "search"

    def _validate_answer(self, value: Any) -> Any:
        return value

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["searchable"] = True
        initial: list[Choice[Any]] = [
            c for raw in self._call_source_sync("") if isinstance((c := parse_choice(raw)), Choice)
        ]
        d["choices"] = [c.to_dict() for c in initial]
        return d

    def _execute_terminal(self) -> Any:
        t = get_theme()
        self._cursor = 0
        self._filtered: list[Choice[Any]] = []
        self._refresh_filtered("")

        search_buffer = Buffer(
            on_text_changed=lambda buf: self._refresh_filtered(buf.text),
        )

        kb = KeyBindings()

        @kb.add("up")
        def _up(event: KeyPressEvent) -> None:
            if self._filtered:
                self._cursor = (self._cursor - 1) % len(self._filtered)

        @kb.add("down")
        def _down(event: KeyPressEvent) -> None:
            if self._filtered:
                self._cursor = (self._cursor + 1) % len(self._filtered)

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            if self._filtered:
                event.app.exit(result=self._filtered[self._cursor].value)
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
            lines: list[tuple[str, str]] = []
            end = min(len(self._filtered), self.page_size)
            for i in range(end):
                choice = self._filtered[i]
                if i == self._cursor:
                    lines.append((t.pt_bold(t.highlight), f"{t.sym_pointer} {choice.name}"))
                else:
                    lines.append(("", f"  {choice.name}"))
                if i < end - 1:
                    lines.append(("", "\n"))
            if not self._filtered:
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

    async def _execute_terminal_async(self) -> Any:  # pragma: no cover
        t = get_theme()
        self._cursor = 0
        self._filtered: list[Choice[Any]] = []
        # Use sync refresh here since prompt_toolkit buffer callbacks are synchronous
        self._refresh_filtered("")

        search_buffer = Buffer(
            on_text_changed=lambda buf: self._refresh_filtered(buf.text),
        )

        kb = KeyBindings()

        @kb.add("up")
        def _up(event: KeyPressEvent) -> None:
            if self._filtered:
                self._cursor = (self._cursor - 1) % len(self._filtered)

        @kb.add("down")
        def _down(event: KeyPressEvent) -> None:
            if self._filtered:
                self._cursor = (self._cursor + 1) % len(self._filtered)

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            if self._filtered:
                event.app.exit(result=self._filtered[self._cursor].value)
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
            lines: list[tuple[str, str]] = []
            end = min(len(self._filtered), self.page_size)
            for i in range(end):
                choice = self._filtered[i]
                if i == self._cursor:
                    lines.append((t.pt_bold(t.highlight), f"{t.sym_pointer} {choice.name}"))
                else:
                    lines.append(("", f"  {choice.name}"))
                if i < end - 1:
                    lines.append(("", "\n"))
            if not self._filtered:
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
        result = await app.run_async()
        if result is None:
            raise PromptAbortedError("Prompt aborted by user")
        return result

    def _refresh_filtered(self, term: str) -> None:
        raw_choices = self._call_source_sync(term)
        self._filtered = [c for raw in raw_choices if isinstance((c := parse_choice(raw)), Choice) and not c.disabled]
        self._cursor = 0
