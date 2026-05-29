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


_MAX_VALIDATION_RETRIES = 3


def _reset_agent_handshake() -> None:
    global _agent_handshake_sent, _agent_handshake_ack, _agent_step
    _agent_handshake_sent = False
    _agent_handshake_ack = None
    _agent_step = 0


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
    global _agent_handshake_sent
    if _agent_handshake_sent:
        return
    _agent_handshake_sent = True
    from inquirer_ai.version import get_version

    meta: HandshakeMessage = {
        "kind": "handshake",
        "protocol": "inquirer-ai",
        "version": get_version(),
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
        global _agent_handshake_ack
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
        """Run one prompt over the stdio agent transport.

        A single unified budget of ``_MAX_VALIDATION_RETRIES`` (3) total
        attempts governs BOTH type-coercion failures and user ``validate()``
        failures (mirroring the socket ``prompt_cycle`` path). The first two
        invalid attempts emit ``validation_error``; the third emits a fatal
        ``error`` and aborts. Filter runs only after validation succeeds.
        """
        global _agent_step
        _send_agent_handshake()
        # Advance the step ONCE per logical prompt; the retry loop below
        # re-sends `_to_agent_dict()` (which reads `_agent_step`) on each
        # validation retry, so every re-send reuses this same step value.
        _agent_step += 1

        retries_used = 0
        while retries_used < _MAX_VALIDATION_RETRIES:
            self._send_agent_json(self._to_agent_dict())

            line = self._read_agent_line()
            if not line:
                # Empty line / EOF / closed stdin => immediate fatal abort (not a retry).
                msg = 'No response received (stdin closed). Expected JSON like: {"answer": "<value>"}'
                self._send_agent_json({"kind": "error", "message": msg})
                raise PromptAbortedError(msg)

            try:
                raw_response: Any = json.loads(line)
            except json.JSONDecodeError as e:
                if not self._agent_retry(f"Invalid JSON response: {e}", retries_used):
                    raise ValidationError(f"Invalid JSON response: {e}") from e
                retries_used += 1
                continue

            if not _is_json_dict(raw_response) or "answer" not in raw_response:
                msg = 'Answer must be a JSON object with an "answer" field'
                if not self._agent_retry(msg, retries_used):
                    raise ValidationError(msg)
                retries_used += 1
                continue

            answer: Any = raw_response["answer"]
            try:
                result = self._validate_answer(answer)
                error = self._run_user_validation(result)
            except ValidationError as e:
                if not self._agent_retry(str(e), retries_used):
                    raise
                retries_used += 1
                continue
            if error:
                if not self._agent_retry(error, retries_used):
                    raise ValidationError(error)
                retries_used += 1
                continue

            if self.filter_fn:
                result = self.filter_fn(result)
            return result

        # Should not reach here, but satisfy type checker
        raise ValidationError("Maximum validation retries exceeded")  # pragma: no cover

    def _agent_retry(self, message: str, retries_used: int) -> bool:
        """Emit a validation_error and report whether a retry remains.

        Returns True when another attempt is allowed (a ``validation_error``
        was sent), or False when the budget is exhausted — in which case the
        caller emits the fatal ``error`` and raises.
        """
        if retries_used + 1 >= _MAX_VALIDATION_RETRIES:
            self._send_agent_json({"kind": "error", "message": message})
            return False
        self._send_agent_json({"kind": "validation_error", "message": message})
        return True

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

    def _print_success(self, result: T) -> None:
        from inquirer_ai.theme import RESET, get_theme

        t = get_theme()
        display = self.transformer(result) if self.transformer else self._format_answer(result)
        print(f"{t.ansi(t.success)}{t.sym_success}{RESET} {self.message} {t.ansi(t.answer)}{display}{RESET}")

    def _terminal_result(self) -> T:
        """Run a terminal prompt, applying user validate() then filter().

        ``validate()`` runs on the coerced value BEFORE ``filter()`` (R11).
        Prompts that implement their own retry loop already call
        ``_run_user_validation`` themselves; re-running it here is idempotent
        for an accepted value.
        """
        from inquirer_ai.theme import RESET, get_theme

        while True:
            try:
                result = self._execute_terminal()
            except EOFError:
                raise PromptAbortedError("Prompt aborted (stdin closed)") from None
            error = self._run_user_validation(result)
            if error:
                t = get_theme()
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                continue
            if self.filter_fn:
                result = self.filter_fn(result)
            self._print_success(result)
            return result

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

        if is_agent_mode():
            # _execute_agent applies a single unified retry budget covering
            # validate() and filter() — do not re-run them here.
            return self._execute_agent()

        return self._terminal_result()

    async def _read_agent_line_async(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_agent_line)

    async def _execute_agent_async(self) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_agent)

    async def _execute_terminal_async(self) -> T:
        return self._execute_terminal()

    async def execute_async(self) -> T:
        if is_agent_mode():
            return await self._execute_agent_async()

        from inquirer_ai.theme import RESET, get_theme

        while True:
            try:
                result = await self._execute_terminal_async()
            except EOFError:
                raise PromptAbortedError("Prompt aborted (stdin closed)") from None

            error = self._run_user_validation(result)
            if error:
                t = get_theme()
                print(f"{t.ansi(t.error)}  {error}{RESET}")
                continue

            if self.filter_fn:
                result = self.filter_fn(result)

            self._print_success(result)

            return result
