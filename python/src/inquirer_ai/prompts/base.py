from __future__ import annotations

import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import IO, Any, Generic, TypeVar

from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode

T = TypeVar("T")
TextIO = IO[str]

_agent_handshake_sent = False
_agent_handshake_ack: dict[str, Any] | None = None
_agent_step = 0
_agent_pushback_line: str | None = None

_MAX_VALIDATION_RETRIES = 3


def _reset_agent_handshake() -> None:
    global _agent_handshake_sent, _agent_handshake_ack, _agent_step, _agent_pushback_line
    _agent_handshake_sent = False
    _agent_handshake_ack = None
    _agent_step = 0
    _agent_pushback_line = None


def _get_agent_out() -> TextIO:
    fd_out = os.environ.get("INQUIRER_AI_FD_OUT")
    if fd_out is not None:
        return os.fdopen(int(fd_out), "w", closefd=False)
    return sys.stdout


def _get_agent_in() -> TextIO:
    fd_in = os.environ.get("INQUIRER_AI_FD_IN")
    if fd_in is not None:
        return os.fdopen(int(fd_in), "r", closefd=False)
    return sys.stdin


def _send_agent_handshake() -> None:
    global _agent_handshake_sent, _agent_handshake_ack, _agent_pushback_line
    if _agent_handshake_sent:
        return
    _agent_handshake_sent = True
    from importlib.metadata import version

    meta = {
        "kind": "handshake",
        "protocol": "inquirer-ai",
        "version": version("inquirer-ai"),
        "format": "jsonl",
        "interaction": "sequential",
        "total": None,
        "description": (
            "Interactive prompt protocol. Prompts are sent one at a time — "
            "read one JSON line from stdout, respond with one JSON line on stdin, "
            "then wait for the next prompt. Do NOT send all answers at once. "
            "Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication."
        ),
        "example_response": {"answer": "<value>"},
    }
    out = _get_agent_out()
    out.write(json.dumps(meta, ensure_ascii=False) + "\n")
    out.flush()


class BasePrompt(ABC, Generic[T]):
    def __init__(
        self,
        message: str,
        *,
        default: Any = None,
        validate: Callable[[T], bool | str | None] | None = None,
        filter: Callable[[T], T] | None = None,
        transformer: Callable[[T], str] | None = None,
    ) -> None:
        self.message = message
        self.default = default
        self.validate_fn = validate
        self.filter_fn = filter
        self.transformer = transformer

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
            "kind": "prompt",
            "type": self.prompt_type,
            "message": self.message,
            "default": self.default,
            "step": _agent_step,
            "total": None,
        }

    def _read_agent_line(self) -> str:
        global _agent_pushback_line, _agent_handshake_ack
        if _agent_pushback_line is not None:
            line = _agent_pushback_line
            _agent_pushback_line = None
            return line
        agent_in = _get_agent_in()
        line = agent_in.readline()
        if line:
            try:
                raw: Any = json.loads(line)
                if isinstance(raw, dict) and raw.get("kind") == "handshake_ack":  # pyright: ignore[reportUnknownMemberType]
                    _agent_handshake_ack = raw  # pyright: ignore[reportUnknownVariableType]
                    return agent_in.readline()
            except json.JSONDecodeError:
                pass
        return line

    def _execute_agent(self) -> T:
        global _agent_step
        _send_agent_handshake()
        _agent_step += 1

        for attempt in range(_MAX_VALIDATION_RETRIES):
            out = _get_agent_out()
            payload = self._to_agent_dict()
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            out.flush()

            line = self._read_agent_line()
            if not line:
                msg = 'No response received (stdin closed). Expected JSON like: {"answer": "<value>"}'
                out2 = _get_agent_out()
                out2.write(json.dumps({"kind": "error", "message": msg}, ensure_ascii=False) + "\n")
                out2.flush()
                raise PromptAbortedError(msg)
            try:
                response = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValidationError(f'Invalid JSON response: {e}. Expected JSON like: {{"answer": "<value>"}}') from e
            if not isinstance(response, dict) or "answer" not in response:
                raise ValidationError(
                    f'Response must be a JSON object with an "answer" key, '
                    f'e.g. {{"answer": "<value>"}}. Got: {line.strip()}'
                )
            try:
                return self._validate_answer(response["answer"])  # pyright: ignore[reportUnknownArgumentType]
            except ValidationError as e:
                if attempt < _MAX_VALIDATION_RETRIES - 1:
                    out3 = _get_agent_out()
                    out3.write(json.dumps({"kind": "validation_error", "message": str(e)}, ensure_ascii=False) + "\n")
                    out3.flush()
                    continue
                raise

        # Should not reach here, but satisfy type checker
        raise ValidationError("Maximum validation retries exceeded")  # pragma: no cover

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

        retries = 0
        while True:
            try:
                result = self._execute_agent() if agent else self._execute_terminal()
            except EOFError:
                raise PromptAbortedError("Prompt aborted (stdin closed)") from None

            if self.filter_fn:
                result = self.filter_fn(result)

            error = self._run_user_validation(result)
            if error:
                if agent:
                    retries += 1
                    if retries >= _MAX_VALIDATION_RETRIES:
                        raise ValidationError(error)
                    out = _get_agent_out()
                    out.write(json.dumps({"kind": "validation_error", "message": error}, ensure_ascii=False) + "\n")
                    out.flush()
                    continue
                t = get_theme()
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                continue

            if not agent:
                t = get_theme()
                display = self.transformer(result) if self.transformer else self._format_answer(result)
                print(f"{t.ansi(t.success)}{t.sym_success}{RESET} {self.message} {t.ansi(t.answer)}{display}{RESET}")

            return result

    async def _read_agent_line_async(self) -> str:
        global _agent_pushback_line, _agent_handshake_ack
        if _agent_pushback_line is not None:
            line = _agent_pushback_line
            _agent_pushback_line = None
            return line
        agent_in = _get_agent_in()
        line = await asyncio.get_running_loop().run_in_executor(None, agent_in.readline)
        if line:
            try:
                raw: Any = json.loads(line)
                if isinstance(raw, dict) and raw.get("kind") == "handshake_ack":  # pyright: ignore[reportUnknownMemberType]
                    _agent_handshake_ack = raw  # pyright: ignore[reportUnknownVariableType]
                    return await asyncio.get_running_loop().run_in_executor(None, agent_in.readline)
            except json.JSONDecodeError:
                pass
        return line

    async def _execute_agent_async(self) -> T:
        global _agent_step
        _send_agent_handshake()
        _agent_step += 1

        for attempt in range(_MAX_VALIDATION_RETRIES):
            out = _get_agent_out()
            payload = self._to_agent_dict()
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            out.flush()

            line = await self._read_agent_line_async()
            if not line:
                msg = 'No response received (stdin closed). Expected JSON like: {"answer": "<value>"}'
                out2 = _get_agent_out()
                out2.write(json.dumps({"kind": "error", "message": msg}, ensure_ascii=False) + "\n")
                out2.flush()
                raise PromptAbortedError(msg)
            try:
                response = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValidationError(f'Invalid JSON response: {e}. Expected JSON like: {{"answer": "<value>"}}') from e
            if not isinstance(response, dict) or "answer" not in response:
                raise ValidationError(
                    f'Response must be a JSON object with an "answer" key, '
                    f'e.g. {{"answer": "<value>"}}. Got: {line.strip()}'
                )
            try:
                return self._validate_answer(response["answer"])  # pyright: ignore[reportUnknownArgumentType]
            except ValidationError as e:
                if attempt < _MAX_VALIDATION_RETRIES - 1:
                    out3 = _get_agent_out()
                    out3.write(json.dumps({"kind": "validation_error", "message": str(e)}, ensure_ascii=False) + "\n")
                    out3.flush()
                    continue
                raise

        # Should not reach here, but satisfy type checker
        raise ValidationError("Maximum validation retries exceeded")  # pragma: no cover

    async def _execute_terminal_async(self) -> T:
        return self._execute_terminal()

    async def execute_async(self) -> T:
        from inquirer_ai.theme import RESET, get_theme

        agent = is_agent_mode()

        retries = 0
        while True:
            try:
                result = await self._execute_agent_async() if agent else await self._execute_terminal_async()
            except EOFError:
                raise PromptAbortedError("Prompt aborted (stdin closed)") from None

            if self.filter_fn:
                result = self.filter_fn(result)

            error = self._run_user_validation(result)
            if error:
                if agent:
                    retries += 1
                    if retries >= _MAX_VALIDATION_RETRIES:
                        raise ValidationError(error)
                    out = _get_agent_out()
                    out.write(json.dumps({"kind": "validation_error", "message": error}, ensure_ascii=False) + "\n")
                    out.flush()
                    continue
                t = get_theme()
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                continue

            if not agent:
                t = get_theme()
                display = self.transformer(result) if self.transformer else self._format_answer(result)
                print(f"{t.ansi(t.success)}{t.sym_success}{RESET} {self.message} {t.ansi(t.answer)}{display}{RESET}")

            return result
