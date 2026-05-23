from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import PathCompleter as PTPathCompleter
from prompt_toolkit.formatted_text import FormattedText

from inquirer_ai.prompts.base import BasePrompt
from inquirer_ai.theme import get_theme


class PathPrompt(BasePrompt[str]):
    def __init__(
        self,
        message: str,
        *,
        default: str | None = None,
        only_directories: bool = False,
        file_filter: Callable[[str], bool] | None = None,
        validate: Callable[[str], bool | str | None] | None = None,
        filter: Callable[[str], str] | None = None,
        transformer: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(message, default=default, validate=validate, filter=filter, transformer=transformer)
        self.only_directories = only_directories
        self.file_filter = file_filter

    @property
    def prompt_type(self) -> str:
        return "path"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["only_directories"] = self.only_directories
        return d

    def _execute_terminal(self) -> str:
        t = get_theme()
        suffix = f" ({self.default})" if self.default is not None else ""
        message = FormattedText(
            [
                (t.pt(t.question), f"{t.sym_question} "),
                ("bold", f"{self.message}{suffix}: "),
            ]
        )
        completer = PTPathCompleter(
            only_directories=self.only_directories,
            file_filter=self.file_filter,
            expanduser=True,
        )
        result = pt_prompt(message, completer=completer)
        if not result and self.default is not None:
            result = self.default
        return result
