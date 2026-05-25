from __future__ import annotations

from abc import abstractmethod
from typing import Any, TypedDict, TypeVar

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window

from inquirer_ai.choice import Choice, ChoiceItem, RawChoice, parse_choice
from inquirer_ai.exceptions import InvalidChoiceError, PromptAbortedError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme

T = TypeVar("T")


class PromptState(TypedDict):
    """State dictionary for choice-based prompts."""

    cursor: int


class ChoiceBasePrompt(BasePrompt[T]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[RawChoice],
        page_size: int = 10,
        loop: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        if not choices:
            raise InvalidChoiceError("choices cannot be empty")
        self.items: list[ChoiceItem] = [parse_choice(c) for c in choices]
        self.choices: list[Choice[Any]] = [c for c in self.items if isinstance(c, Choice)]
        if not any(not c.disabled for c in self.choices):
            raise InvalidChoiceError("choices must contain at least one selectable item")
        self.page_size = page_size
        self.loop = loop

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [c.to_dict() for c in self.items]
        return d

    @abstractmethod
    def _build_keybindings(self, kb: KeyBindings, choices: list[Choice[Any]], state: PromptState) -> None: ...

    @abstractmethod
    def _format_choice_line(self, index: int, item: ChoiceItem, state: PromptState) -> tuple[str, str]: ...

    @abstractmethod
    def _get_result(self, state: PromptState) -> Any: ...

    def _is_selectable(self, index: int) -> bool:
        item = self.items[index]
        return isinstance(item, Choice) and not item.disabled

    def _selectable_indices(self) -> list[int]:
        return [i for i in range(len(self.items)) if self._is_selectable(i)]

    def _init_cursor(self) -> int:
        return 0

    def _move_cursor(self, current: int, direction: int) -> int:
        indices = self._selectable_indices()
        try:
            pos = indices.index(current)
        except ValueError:
            return indices[0]
        new_pos = pos + direction
        new_pos = new_pos % len(indices) if self.loop else max(0, min(new_pos, len(indices) - 1))
        return indices[new_pos]

    def _execute_terminal(self) -> T:
        t = get_theme()
        items = self.items
        state: PromptState = {"cursor": self._init_cursor()}

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event: KeyPressEvent) -> None:
            state["cursor"] = self._move_cursor(state["cursor"], -1)

        @kb.add("down")
        @kb.add("j")
        def _down(event: KeyPressEvent) -> None:
            state["cursor"] = self._move_cursor(state["cursor"], 1)

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            event.app.exit(result=self._get_result(state))

        @kb.add("c-c")
        def _abort(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        self._build_keybindings(kb, self.choices, state)

        def get_message() -> FormattedText:
            return FormattedText(
                [
                    (t.pt(t.question), f"{t.sym_question} "),
                    ("bold", self.message),
                ]
            )

        def _visible_range() -> tuple[int, int]:
            cursor = state["cursor"]
            total = len(items)
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
                lines.append(self._format_choice_line(i, items[i], state))
                if i < end - 1:
                    lines.append(("", "\n"))
            if end < len(items):
                lines.append(("", "\n"))
                lines.append((t.pt(t.muted), "  (more below)"))
            return FormattedText(lines)

        layout = Layout(
            HSplit(
                [
                    Window(FormattedTextControl(get_message), height=1),
                    Window(FormattedTextControl(get_formatted_choices)),
                ]
            )
        )

        app: Application[Any] = Application(layout=layout, key_bindings=kb, full_screen=False, erase_when_done=True)
        result = app.run()
        if result is None:
            raise PromptAbortedError("Prompt aborted by user")
        return result

    async def _execute_terminal_async(self) -> T:  # pragma: no cover
        t = get_theme()
        items = self.items
        state: PromptState = {"cursor": self._init_cursor()}

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event: KeyPressEvent) -> None:
            state["cursor"] = self._move_cursor(state["cursor"], -1)

        @kb.add("down")
        @kb.add("j")
        def _down(event: KeyPressEvent) -> None:
            state["cursor"] = self._move_cursor(state["cursor"], 1)

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            event.app.exit(result=self._get_result(state))

        @kb.add("c-c")
        def _abort(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        self._build_keybindings(kb, self.choices, state)

        def get_message() -> FormattedText:
            return FormattedText(
                [
                    (t.pt(t.question), f"{t.sym_question} "),
                    ("bold", self.message),
                ]
            )

        def _visible_range() -> tuple[int, int]:
            cursor = state["cursor"]
            total = len(items)
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
                lines.append(self._format_choice_line(i, items[i], state))
                if i < end - 1:
                    lines.append(("", "\n"))
            if end < len(items):
                lines.append(("", "\n"))
                lines.append((t.pt(t.muted), "  (more below)"))
            return FormattedText(lines)

        layout = Layout(
            HSplit(
                [
                    Window(FormattedTextControl(get_message), height=1),
                    Window(FormattedTextControl(get_formatted_choices)),
                ]
            )
        )

        app: Application[Any] = Application(layout=layout, key_bindings=kb, full_screen=False, erase_when_done=True)
        result = await app.run_async()
        if result is None:
            raise PromptAbortedError("Prompt aborted by user")
        return result
