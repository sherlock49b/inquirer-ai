from __future__ import annotations

import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import IO, Any, Generic, Literal, TypedDict, TypeGuard, TypeVar

from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode

T = TypeVar("T")
TextIO = IO[str]


def _is_json_dict(value: object) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)

_agent_handshake_sent = False
_agent_handshake_ack: dict[str, Any] | None = None
_agent_step = 0
_agent_pushback_line: str | None = None


class HandshakeMessage(TypedDict):
    """Protocol handshake message sent at connection start."""

    kind: Literal["handshake"]
    protocol: str
    version: str
    format: str
    interaction: str
    total: None
    description: str
    example_response: dict[str, str]


class AgentResponse(TypedDict):
    """Response from the agent containing an answer."""

    answer: Any  # Genuinely Any — values come from user-provided JSON


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
        try:
            return os.fdopen(int(fd_out), "w", closefd=False)
        except (ValueError, OSError) as exc:
            print(
                f"inquirer-ai: invalid INQUIRER_AI_FD_OUT={fd_out!r} ({exc}), falling back to stdout",
                file=sys.stderr,
            )
    return sys.stdout


def _get_agent_in() -> TextIO:
    fd_in = os.environ.get("INQUIRER_AI_FD_IN")
    if fd_in is not None:
        try:
            return os.fdopen(int(fd_in), "r", closefd=False)
        except (ValueError, OSError) as exc:
            print(
                f"inquirer-ai: invalid INQUIRER_AI_FD_IN={fd_in!r} ({exc}), falling back to stdin",
                file=sys.stderr,
            )
    return sys.stdin


def _send_agent_handshake() -> None:
    global _agent_handshake_sent, _agent_handshake_ack, _agent_pushback_line
    if _agent_handshake_sent:
        return
    _agent_handshake_sent = True
    from importlib.metadata import version

    meta: HandshakeMessage = {
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
        default: T | None = None,
        validate: Callable[[T], bool | str | None] | None = None,
        filter: Callable[[T], T] | None = None,
        transformer: Callable[[T], str] | None = None,
    ) -> None:
        self.message = message
        self.default: T | None = default
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
        line = line.strip()
        if line:
            try:
                raw: Any = json.loads(line)
            except json.JSONDecodeError:
                return line
            if _is_json_dict(raw) and raw.get("kind") == "handshake_ack":
                _agent_handshake_ack = raw
                next_line = agent_in.readline()
                return next_line.strip()
        return line

    @staticmethod
    def _send_agent_json(data: dict[str, Any]) -> None:
        out = _get_agent_out()
        out.write(json.dumps(data, ensure_ascii=False) + "\n")
        out.flush()

    def _execute_agent(self) -> T:
        global _agent_step
        _send_agent_handshake()
        _agent_step += 1

        for attempt in range(_MAX_VALIDATION_RETRIES):
            self._send_agent_json(self._to_agent_dict())

            line = self._read_agent_line()
            if not line:
                msg = 'No response received (stdin closed). Expected JSON like: {"answer": "<value>"}'
                self._send_agent_json({"kind": "error", "message": msg})
                raise PromptAbortedError(msg)
            try:
                raw_response: Any = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValidationError(f'Invalid JSON response: {e}. Expected JSON like: {{"answer": "<value>"}}') from e
            if not _is_json_dict(raw_response) or "answer" not in raw_response:
                raise ValidationError(
                    f'Response must be a JSON object with an "answer" key, '
                    f'e.g. {{"answer": "<value>"}}. Got: {line.strip()}'
                )
            answer: Any = raw_response["answer"]
            try:
                return self._validate_answer(answer)
            except ValidationError as e:
                if attempt < _MAX_VALIDATION_RETRIES - 1:
                    self._send_agent_json({"kind": "validation_error", "message": str(e)})
                    continue
                raise

        # Should not reach here, but satisfy type checker
        raise ValidationError("Maximum validation retries exceeded")  # pragma: no cover

    def _run_user_validation(self, value: T) -> str | None:
        if not self.validate_fn:
            return None
        try:
            result = self.validate_fn(value)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(str(exc) or f"{type(exc).__name__} in validator") from exc
        if result is True or result is None:
            return None
        if isinstance(result, str):
            return result
        return "Validation failed"

    def _handle_validation_error_loop(self, error: str, is_agent: bool, retries: int) -> int:
        """Handle a validation error during the execute loop.

        Returns the updated retry count.  Raises ValidationError when
        the agent-mode retry budget is exhausted.
        """
        from inquirer_ai.theme import RESET, get_theme

        if is_agent:
            retries += 1
            if retries >= _MAX_VALIDATION_RETRIES:
                raise ValidationError(error)
            self._send_agent_json({"kind": "validation_error", "message": error})
            return retries
        t = get_theme()
        print(f"{t.ansi(t.error)}  {error}{RESET}")
        return retries

    def _print_success(self, result: T) -> None:
        from inquirer_ai.theme import RESET, get_theme

        t = get_theme()
        display = self.transformer(result) if self.transformer else self._format_answer(result)
        print(f"{t.ansi(t.success)}{t.sym_success}{RESET} {self.message} {t.ansi(t.answer)}{display}{RESET}")

    def execute(self) -> T:
        from inquirer_ai.socket_transport import get_socket_transport

        transport = get_socket_transport()
        if transport is not None:
            return transport.prompt_cycle(
                self._to_agent_dict(),
                self._validate_answer,
                filter_fn=self.filter_fn,
                user_validate=self._run_user_validation,
            )

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
                retries = self._handle_validation_error_loop(error, agent, retries)
                continue

            if not agent:
                self._print_success(result)

            return result

    async def _read_agent_line_async(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_agent_line)

    async def _execute_agent_async(self) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_agent)

    async def _execute_terminal_async(self) -> T:
        return self._execute_terminal()

    async def execute_async(self) -> T:
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
                retries = self._handle_validation_error_loop(error, agent, retries)
                continue

            if not agent:
                self._print_success(result)

            return result
