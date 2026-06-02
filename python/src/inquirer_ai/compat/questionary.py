"""Drop-in replacement for questionary, backed by inquirer-ai.

Usage in commitizen or any questionary-based project:

    # Replace:
    #   import questionary
    # With:
    #   from inquirer_ai.compat import questionary

All public questionary APIs used by commitizen are supported:
    questionary.prompt(questions, style=...)
    questionary.select(...).ask()
    questionary.confirm(...).ask()
    questionary.checkbox(...).ask()
    questionary.text(...).ask()
    questionary.Choice(title=..., value=..., checked=...)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from inquirer_ai.choice import Choice as InquirerChoice
from inquirer_ai.choice import Separator
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


class Choice:
    """questionary.Choice compatible wrapper."""

    def __init__(
        self,
        title: str,
        value: Any = None,
        *,
        checked: bool = False,
        disabled: str | None = None,
        shortcut_key: str | None = None,
        description: str | None = None,
    ) -> None:
        self.title = title
        self.value = value if value is not None else title
        self.checked = checked
        self.disabled = disabled
        self.shortcut_key = shortcut_key
        self.description = description

    def to_inquirer(self) -> InquirerChoice[Any]:
        return InquirerChoice(
            name=self.title,
            value=self.value,
            disabled=self.disabled or False,
            description=self.description,
        )


class _LazyPrompt:
    """Wraps a prompt to provide .ask() / .unsafe_ask() / .ask_async() interface."""

    def __init__(self, prompt_fn: Callable[[], Any]) -> None:
        self._fn = prompt_fn

    def ask(self) -> Any:
        try:
            return self._fn()
        except KeyboardInterrupt:
            return None

    def unsafe_ask(self) -> Any:
        return self._fn()

    async def ask_async(self) -> Any:
        try:
            return await self._run_async()
        except KeyboardInterrupt:
            return None

    async def unsafe_ask_async(self) -> Any:
        return await self._run_async()

    async def _run_async(self) -> Any:
        # Do not block the event loop: run the (potentially blocking) prompt in
        # an executor thread (pysock-7).
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fn)


def _convert_choices(raw_choices: list[Any]) -> list[Any]:
    result: list[Any] = []
    for c in raw_choices:
        if isinstance(c, Choice):
            result.append(c.to_inquirer())
        elif isinstance(c, (Separator, dict)):
            result.append(c)
        else:
            result.append(str(c))
    return result


def _get_defaults(raw_choices: list[Any]) -> list[str]:
    defaults: list[str] = []
    for c in raw_choices:
        if isinstance(c, Choice) and c.checked:
            defaults.append(c.value)
    return defaults


def select(
    message: str,
    choices: list[Any] | None = None,
    *,
    default: Any = None,
    style: Any = None,
    **kwargs: Any,
) -> _LazyPrompt:
    converted = _convert_choices(choices or [])

    def run() -> Any:
        return SelectPrompt(
            message,
            choices=converted,
            default=default,
        ).execute()

    return _LazyPrompt(run)


def confirm(
    message: str,
    *,
    default: bool = True,
    style: Any = None,
    **kwargs: Any,
) -> _LazyPrompt:
    def run() -> bool:
        return ConfirmPrompt(message, default=default).execute()

    return _LazyPrompt(run)


def checkbox(
    message: str,
    choices: list[Any] | None = None,
    *,
    style: Any = None,
    **kwargs: Any,
) -> _LazyPrompt:
    converted = _convert_choices(choices or [])
    defaults = _get_defaults(choices or [])

    def run() -> list[Any]:
        return CheckboxPrompt(
            message,
            choices=converted,
            default=defaults if defaults else None,
        ).execute()

    return _LazyPrompt(run)


def text(
    message: str,
    *,
    default: str = "",
    style: Any = None,
    filter: Callable[[str], str] | None = None,
    **kwargs: Any,
) -> _LazyPrompt:
    def run() -> str:
        return TextPrompt(
            message,
            default=default or None,
            filter=filter,
        ).execute()

    return _LazyPrompt(run)


def prompt(
    questions: list[dict[str, Any]],
    *,
    style: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """questionary.prompt() compatible — processes a list of question dicts."""
    answers: dict[str, Any] = {}
    for idx, q in enumerate(questions):
        qtype = q.get("type", "input")
        # Unnamed questions must not collide on answers[""] — fall back to a
        # positional key (pysock-6).
        name = q.get("name") or str(idx)
        message = q.get("message", "")

        # questionary's `when` is a predicate over the accumulated answers.
        when_fn = q.get("when")
        if when_fn is not None and not when_fn(answers):
            continue

        # Thread the standard callbacks to every branch (pysock-6).
        common: dict[str, Any] = {}
        if q.get("validate") is not None:
            common["validate"] = q["validate"]
        if q.get("filter") is not None:
            common["filter"] = q["filter"]

        if qtype == "list":
            converted = _convert_choices(q.get("choices", []))
            result = SelectPrompt(message, choices=converted, default=q.get("default"), **common).execute()
        elif qtype == "input":
            result = TextPrompt(message, default=q.get("default") or None, **common).execute()
        elif qtype == "confirm":
            result = ConfirmPrompt(message, default=q.get("default", True), **common).execute()
        elif qtype == "checkbox":
            raw_choices = q.get("choices", [])
            converted = _convert_choices(raw_choices)
            defaults = _get_defaults(raw_choices)
            result = CheckboxPrompt(message, choices=converted, default=defaults or None, **common).execute()
        else:
            result = TextPrompt(message, default=q.get("default") or None, **common).execute()

        answers[name] = result

    return answers
