from __future__ import annotations

import atexit
import contextlib
import json
import os
import signal
import socket
import stat
import sys
import types
from collections.abc import Callable
from typing import IO, Any, TypeGuard, TypeVar

from inquirer_ai.exceptions import ValidationError

T = TypeVar("T")


def _is_json_dict(value: object) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)


_MAX_RETRIES = 3
# Maximum size of a single answer line accepted from the socket (1 MiB).
_MAX_LINE_BYTES = 1_048_576
# Unix sun_path is limited (typically 108 bytes); stay safely below.
_MAX_SOCKET_PATH = 104

# Sentinel marking a failed JSON parse (distinct from any valid JSON value).
_SENTINEL = object()


class SocketTransportError(RuntimeError):
    """Raised when the socket transport cannot be safely started."""


def _default_socket_path() -> str:
    return f"/tmp/inquirer-ai-{os.getpid()}.sock"


def _validate_explicit_path(path: str) -> None:
    """Validate a user-supplied INQUIRER_AI_SOCKET path (R10)."""
    if not path:
        raise SocketTransportError("INQUIRER_AI_SOCKET must be a non-empty path")
    if not os.path.isabs(path):
        raise SocketTransportError(f"INQUIRER_AI_SOCKET must be an absolute path, got {path!r}")
    if len(path.encode("utf-8")) >= _MAX_SOCKET_PATH:
        raise SocketTransportError(f"INQUIRER_AI_SOCKET path too long (>= {_MAX_SOCKET_PATH} bytes): {path!r}")
    parent = os.path.dirname(path) or "."
    if not os.path.isdir(parent):
        raise SocketTransportError(f"INQUIRER_AI_SOCKET parent directory does not exist: {parent!r}")


def _prepare_socket_path(path: str) -> None:
    """lstat the target; unlink only if it is a stale socket (R10).

    Never follows symlinks and never removes a non-socket file/dir. Removal
    errors (directory, permission) are surfaced as a clean handled error.
    """
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise SocketTransportError(f"Cannot stat socket path {path!r}: {exc}") from exc
    if not stat.S_ISSOCK(st.st_mode):
        raise SocketTransportError(
            f"Refusing to start: {path!r} exists and is not a socket "
            f"(it is a {'symlink' if stat.S_ISLNK(st.st_mode) else 'file or directory'})"
        )
    try:
        os.unlink(path)
    except OSError as exc:
        raise SocketTransportError(f"Cannot remove stale socket {path!r}: {exc}") from exc


class SocketTransport:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or _default_socket_path()
        self._stdout_handshake_sent = False
        self._socket_handshake_sent = False
        self._step = 0
        self._cleaned_up = False

        _prepare_socket_path(self.path)

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._server.bind(self.path)
        except OSError as exc:
            with contextlib.suppress(Exception):
                self._server.close()
            raise SocketTransportError(f"Cannot bind socket {self.path!r}: {exc}") from exc
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)
        self._server.listen(1)

        self._send_stdout_handshake()

        atexit.register(self.cleanup)
        self._prev_sigint = signal.getsignal(signal.SIGINT)
        self._prev_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._make_signal_handler(self._prev_sigint))
        signal.signal(signal.SIGTERM, self._make_signal_handler(self._prev_sigterm))

    def _make_signal_handler(self, prev: Any) -> Callable[[int, types.FrameType | None], None]:
        def _handler(signo: int, frame: types.FrameType | None) -> None:
            self.cleanup()
            if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
                prev(signo, frame)
            sys.exit(0)

        return _handler

    def cleanup(self) -> None:
        if self._cleaned_up:
            return
        self._cleaned_up = True
        with contextlib.suppress(Exception):
            self._server.close()
        with contextlib.suppress(FileNotFoundError, IsADirectoryError, OSError):
            os.unlink(self.path)

    def dispose(self) -> None:
        """Fully tear down the transport and restore process-global state.

        Cleans up the socket, unregisters the atexit hook, and restores the
        SIGINT/SIGTERM handlers that were installed during construction. Safe
        to call more than once (idempotent via the cleanup guard).
        """
        self.cleanup()
        atexit.unregister(self.cleanup)
        with contextlib.suppress(Exception):
            signal.signal(signal.SIGINT, self._prev_sigint)
        with contextlib.suppress(Exception):
            signal.signal(signal.SIGTERM, self._prev_sigterm)

    def _send_stdout_handshake(self) -> None:
        if self._stdout_handshake_sent:
            return
        self._stdout_handshake_sent = True
        payload = self._handshake_payload()
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _handshake_payload(self) -> dict[str, Any]:
        from inquirer_ai.version import get_version

        return {
            "kind": "handshake",
            "protocol": "inquirer-ai",
            "version": get_version(),
            "format": "jsonl",
            "socket": self.path,
            "interaction": "sequential",
            "total": None,
            "description": (
                "Interactive prompt protocol over Unix socket. "
                "Connect to read a prompt, send a JSON answer, receive status. "
                "One connection per prompt."
            ),
            "example_response": {"answer": "<value>"},
        }

    def prompt_cycle(
        self,
        payload: dict[str, Any],
        validate: Callable[[Any], T],
        filter_fn: Callable[[T], T] | None = None,
        user_validate: Callable[[T], str | None] | None = None,
    ) -> T:
        # Advance the global step ONCE per logical prompt; every re-send of
        # this prompt (validation retries, connection re-accepts) reuses the
        # same step value via the fixed `payload` built here.
        self._step += 1
        payload = {**payload, "step": self._step}

        retries_used = 0

        while retries_used < _MAX_RETRIES:
            conn, _ = self._server.accept()
            rfile = conn.makefile("r")
            wfile = conn.makefile("w")

            try:
                if not self._socket_handshake_sent:
                    self._write(wfile, self._handshake_payload())
                    self._socket_handshake_sent = True

                self._write(wfile, payload)

                while retries_used < _MAX_RETRIES:
                    line = rfile.readline(_MAX_LINE_BYTES + 1)
                    if not line or not line.strip():
                        break

                    if len(line.encode("utf-8", "surrogatepass")) > _MAX_LINE_BYTES:
                        # The bounded read truncated an over-long line; discard
                        # the rest of the physical line so the next read starts
                        # cleanly, then consume a retry (R10).
                        if not line.endswith("\n"):
                            self._drain_line(rfile)
                        retries_used += 1
                        if self._emit(wfile, "Answer line exceeds maximum size", retries_used):
                            continue
                        raise ValidationError("Answer line exceeds maximum size")

                    line = line.strip()

                    parsed, fatal = self._parse_line(wfile, line, retries_used)
                    if parsed is _SENTINEL:
                        retries_used += 1
                        if fatal:
                            raise ValidationError(f"Invalid JSON response: {line}")
                        continue
                    raw_parsed: Any = parsed

                    if _is_json_dict(raw_parsed) and raw_parsed.get("kind") == "handshake_ack":
                        line = rfile.readline(_MAX_LINE_BYTES + 1)
                        if not line or not line.strip():
                            break
                        line = line.strip()
                        parsed, fatal = self._parse_line(wfile, line, retries_used)
                        if parsed is _SENTINEL:
                            retries_used += 1
                            if fatal:
                                raise ValidationError(f"Invalid JSON response: {line}")
                            continue
                        raw_parsed = parsed

                    if not _is_json_dict(raw_parsed) or "answer" not in raw_parsed:
                        retries_used += 1
                        msg = 'Answer must be a JSON object with an "answer" field'
                        if self._emit(wfile, msg, retries_used):
                            continue
                        raise ValidationError(msg)

                    answer: Any = raw_parsed["answer"]

                    try:
                        result = validate(answer)
                        error = user_validate(result) if user_validate else None
                    except ValidationError as e:
                        retries_used += 1
                        if self._emit(wfile, str(e), retries_used):
                            continue
                        raise
                    except Exception as e:
                        # A non-ValidationError raised by user validate() is fatal
                        # but must be reported as an error before exit (R10).
                        msg = str(e) or f"{type(e).__name__} in validator"
                        self._write(wfile, {"kind": "error", "message": msg})
                        raise ValidationError(msg) from e

                    if error:
                        retries_used += 1
                        if self._emit(wfile, error, retries_used):
                            continue
                        raise ValidationError(error)

                    if filter_fn:
                        result = filter_fn(result)
                    # Do not lose a validated answer if writing "accepted" fails
                    # on a broken pipe (R10): compute, write under suppression, return.
                    with contextlib.suppress(Exception):
                        self._write(wfile, {"status": "accepted"})
                    return result

            except (ConnectionError, BrokenPipeError):
                pass
            finally:
                for f in (rfile, wfile):
                    with contextlib.suppress(Exception):
                        f.close()
                with contextlib.suppress(Exception):
                    conn.close()

        raise ValidationError("Maximum validation retries exceeded")

    @staticmethod
    def _drain_line(rfile: IO[str]) -> None:
        """Consume and discard the remainder of an over-long physical line."""
        while True:
            chunk = rfile.readline(_MAX_LINE_BYTES + 1)
            if not chunk or chunk.endswith("\n"):
                break

    def _parse_line(self, wfile: IO[str], line: str, retries_used: int) -> tuple[Any, bool]:
        """Parse one untrusted JSON line.

        Returns ``(parsed_value, _)`` on success, or ``(_SENTINEL, fatal)`` on
        failure where ``fatal`` is True when the retry budget is exhausted
        (caller raises) and a ``validation_error`` has already been emitted
        otherwise. Never raises on malformed/decoding input (R10).
        """
        try:
            return json.loads(line), False
        except (json.JSONDecodeError, ValueError, RecursionError) as e:
            msg = f"Invalid JSON response: {e}"
            fatal = not self._emit(wfile, msg, retries_used + 1)
            return _SENTINEL, fatal

    def _emit(self, wfile: IO[str], message: str, retries_used: int) -> bool:
        """Emit a validation_error if retries remain, else a fatal error.

        Returns True when the caller should ``continue`` (a ``validation_error``
        was sent), False when the budget is exhausted and the caller must raise.
        """
        if retries_used >= _MAX_RETRIES:
            self._write(wfile, {"kind": "error", "message": message})
            return False
        self._write(wfile, {"kind": "validation_error", "message": message})
        return True

    @staticmethod
    def _write(wfile: IO[str], data: dict[str, Any]) -> None:
        wfile.write(json.dumps(data, ensure_ascii=False) + "\n")
        wfile.flush()


_transport: SocketTransport | None = None
_transport_checked = False


def get_socket_transport() -> SocketTransport | None:
    global _transport, _transport_checked
    if _transport is not None:
        return _transport
    if _transport_checked:
        return None
    _transport_checked = True

    if sys.platform == "win32":
        return None

    from inquirer_ai.mode import is_agent_mode, is_human_mode, is_socket_requested

    # R3: human mode never uses any agent transport.
    if is_human_mode():
        return None
    # Only act as an agent when stdin is not a TTY or a socket/agent mode is requested.
    if not is_agent_mode():
        return None
    # Socket transport requires socket_requested AND not forced to stdio.
    if not is_socket_requested():
        return None
    if os.environ.get("INQUIRER_AI_TRANSPORT", "").lower() == "stdio":
        return None

    path = os.environ.get("INQUIRER_AI_SOCKET")
    if path:
        _validate_explicit_path(path)
        _transport = SocketTransport(path)
    else:
        _transport = SocketTransport()
    return _transport


def reset_socket_transport() -> None:
    global _transport, _transport_checked
    if _transport is not None:
        _transport.dispose()
        _transport = None
    _transport_checked = False
