from __future__ import annotations

from typing import Any

from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt

_PROMPT_MAP: dict[str, type] = {
    "input": TextPrompt,
    "confirm": ConfirmPrompt,
    "select": SelectPrompt,
    "checkbox": CheckboxPrompt,
}


def prompt(questions: list[dict[str, Any]]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for q in questions:
        q = dict(q)
        prompt_type = q.pop("type")
        name = q.pop("name")
        message = q.pop("message")

        cls = _PROMPT_MAP.get(prompt_type)
        if cls is None:
            raise ValueError(f"Unknown prompt type: {prompt_type!r}")

        p = cls(message, **q)
        answers[name] = p.execute()
    return answers
