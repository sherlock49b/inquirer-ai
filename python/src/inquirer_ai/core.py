from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from inquirer_ai.choice import Choice
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.password import PasswordPrompt
from inquirer_ai.prompts.search import SearchPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


class _QuestionRequired(TypedDict):
    type: str
    name: str
    message: str


class Question(_QuestionRequired, total=False):
    default: Any
    choices: list[str | dict[str, Any] | Choice[Any]]
    validate: Callable[[Any], bool | str | None]
    filter: Callable[[Any], Any]
    transformer: Callable[[Any], str]
    when: Callable[[dict[str, Any]], bool]


_PROMPT_MAP: dict[str, type[BasePrompt[Any]]] = {
    "input": TextPrompt,
    "confirm": ConfirmPrompt,
    "select": SelectPrompt,
    "checkbox": CheckboxPrompt,
    "password": PasswordPrompt,
    "number": NumberPrompt,
    "search": SearchPrompt,
}


def prompt(questions: list[Question]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for q in questions:
        when_fn = q.get("when")
        if when_fn is not None and not when_fn(answers):
            continue

        kwargs: dict[str, Any] = {k: v for k, v in q.items() if k not in ("type", "name", "message", "when")}

        cls = _PROMPT_MAP.get(q["type"])
        if cls is None:
            raise ValueError(f"Unknown prompt type: {q['type']!r}")

        p = cls(q["message"], **kwargs)
        answers[q["name"]] = p.execute()
    return answers
