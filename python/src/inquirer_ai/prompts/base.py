from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from typing import Any

from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode


class BasePrompt(ABC):
    def __init__(self, message: str, *, default: Any = None) -> None:
        self.message = message
        self.default = default

    @property
    @abstractmethod
    def prompt_type(self) -> str: ...

    @abstractmethod
    def _execute_terminal(self) -> Any: ...

    @abstractmethod
    def _validate_answer(self, value: Any) -> Any: ...

    def _to_agent_dict(self) -> dict[str, Any]:
        return {
            "type": self.prompt_type,
            "message": self.message,
            "default": self.default,
        }

    def _execute_agent(self) -> Any:
        payload = self._to_agent_dict()
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            raise PromptAbortedError("No response received (stdin closed)")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON response: {e}") from e
        return self._validate_answer(response.get("answer"))

    def execute(self) -> Any:
        if is_agent_mode():
            return self._execute_agent()
        return self._execute_terminal()
