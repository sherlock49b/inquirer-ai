from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.exceptions import InvalidChoiceError, ValidationError
from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import RESET, get_theme


@dataclass
class ExpandChoice:
    key: str
    name: str
    value: Any


class ExpandPrompt(BasePrompt[Any]):
    def __init__(
        self,
        message: str,
        *,
        choices: list[dict[str, Any] | ExpandChoice],
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        if not choices:
            raise InvalidChoiceError("choices cannot be empty")
        self.expand_choices = [self._parse(c) for c in choices]
        keys = [c.key for c in self.expand_choices]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise InvalidChoiceError(f"Duplicate expand keys: {dupes}")

    @staticmethod
    def _parse(raw: dict[str, Any] | ExpandChoice) -> ExpandChoice:
        if isinstance(raw, ExpandChoice):
            return raw
        if "key" not in raw:
            raise InvalidChoiceError("ExpandChoice dict must have a 'key' field")
        key = raw["key"]
        if not isinstance(key, str):
            raise InvalidChoiceError(f"ExpandChoice 'key' must be a string, got {type(key).__name__}")
        return ExpandChoice(
            key=key.lower(),
            name=raw.get("name", key),
            value=raw.get("value", key),
        )

    @property
    def prompt_type(self) -> str:
        return "expand"

    def _validate_answer(self, value: Any) -> Any:
        if isinstance(value, str):
            lower = value.lower()
            for c in self.expand_choices:
                if lower == c.key or value == c.value or value == c.name:
                    return c.value
        # Keys are already lowercased in _parse; advertise them as the valid set.
        valid_repr = ", ".join(json.dumps(c.key) for c in self.expand_choices)
        raise ValidationError(f"Invalid choice: {json.dumps(value)}. Valid: [{valid_repr}]")

    def _format_answer(self, value: Any) -> str:
        for c in self.expand_choices:
            if c.value == value:
                return c.name
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["choices"] = [{"key": c.key, "name": c.name, "value": c.value} for c in self.expand_choices]
        return d

    def _execute_terminal(self) -> Any:
        t = get_theme()
        keys = "/".join(c.key for c in self.expand_choices)
        compact_hint = "(" + "/".join(c.key for c in self.expand_choices) + "/h)"
        expanded = False
        while True:
            if expanded:
                for c in self.expand_choices:
                    print(f"  {c.key}) {c.name}")
                message = FormattedText(
                    [
                        (t.pt(t.question), f"{t.sym_question} "),
                        ("bold", f"{self.message} ({keys}/h): "),
                    ]
                )
            else:
                message = FormattedText(
                    [
                        (t.pt(t.question), f"{t.sym_question} "),
                        ("bold", f"{self.message} {compact_hint}: "),
                    ]
                )
            raw = pt_prompt(message)
            lower = raw.strip().lower()
            if lower == "h" or lower == "help":
                expanded = not expanded
                continue
            for c in self.expand_choices:
                if lower == c.key:
                    return c.value
            print(f"{t.ansi(t.error)}  Invalid key. Press h for help.{RESET}")
