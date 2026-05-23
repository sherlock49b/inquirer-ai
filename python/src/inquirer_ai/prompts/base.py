from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode

T = TypeVar("T")


class BasePrompt(ABC, Generic[T]):
    def __init__(
        self,
        message: str,
        *,
        default: Any = None,
        validate: Callable[[T], bool | str | None] | None = None,
        filter: Callable[[T], T] | None = None,
    ) -> None:
        self.message = message
        self.default = default
        self.validate_fn = validate
        self.filter_fn = filter

    @property
    @abstractmethod
    def prompt_type(self) -> str: ...

    @abstractmethod
    def _execute_terminal(self) -> T: ...

    @abstractmethod
    def _validate_answer(self, value: Any) -> T: ...

    def _format_answer(self, value: T) -> str:
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        return {
            "type": self.prompt_type,
            "message": self.message,
            "default": self.default,
        }

    def _execute_agent(self) -> T:
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

    def _run_user_validation(self, value: T) -> str | None:
        if not self.validate_fn:
            return None
        result = self.validate_fn(value)
        if result is True or result is None:
            return None
        if isinstance(result, str):
            return result
        return "Validation failed"

    def execute(self) -> T:
        from inquirer_ai.theme import RESET, get_theme

        agent = is_agent_mode()

        while True:
            result = self._execute_agent() if agent else self._execute_terminal()

            if self.filter_fn:
                result = self.filter_fn(result)

            error = self._run_user_validation(result)
            if error:
                if agent:
                    raise ValidationError(error)
                t = get_theme()
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                continue

            if not agent:
                t = get_theme()
                display = self._format_answer(result)
                print(f"{t.ansi(t.success)}{t.sym_success}{RESET} {self.message} {t.ansi(t.answer)}{display}{RESET}")

            return result
