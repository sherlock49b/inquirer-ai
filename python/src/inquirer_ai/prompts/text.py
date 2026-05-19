from __future__ import annotations

from typing import Any

from prompt_toolkit import prompt as pt_prompt

from inquirer_ai.prompts.base import BasePrompt


class TextPrompt(BasePrompt):
    @property
    def prompt_type(self) -> str:
        return "input"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default or ""
        return str(value)

    def _execute_terminal(self) -> str:
        suffix = f" ({self.default})" if self.default else ""
        result = pt_prompt(f"? {self.message}{suffix}: ")
        if not result and self.default:
            return self.default
        return result
