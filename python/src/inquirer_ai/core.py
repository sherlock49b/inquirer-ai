from __future__ import annotations

from typing import Any, TypedDict

from inquirer_ai.choice import Choice
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


class _QuestionRequired(TypedDict):
    type: str
    name: str
    message: str


class Question(_QuestionRequired, total=False):
    default: Any
    choices: list[str | dict[str, Any] | Choice]


_PROMPT_MAP: dict[str, type[BasePrompt[Any]]] = {
    "input": TextPrompt,
    "confirm": ConfirmPrompt,
    "select": SelectPrompt,
    "checkbox": CheckboxPrompt,
}


def prompt(questions: list[Question]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for q in questions:
        kwargs: dict[str, Any] = {k: v for k, v in q.items() if k not in ("type", "name", "message")}

        cls = _PROMPT_MAP.get(q["type"])
        if cls is None:
            raise ValueError(f"Unknown prompt type: {q['type']!r}")

        p = cls(q["message"], **kwargs)
        answers[q["name"]] = p.execute()
    return answers
