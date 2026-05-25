from __future__ import annotations

import atexit
import contextlib
import json
import os
import signal
import socket
import sys
import types
from collections.abc import Callable
from typing import IO, Any, TypeGuard, TypeVar

from inquirer_ai.exceptions import ValidationError

T = TypeVar("T")


def _is_json_dict(value: object) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)


_MAX_RETRIES = 3


def _default_socket_path() -> str:
    return f"/tmp/inquirer-ai-{os.getpid()}.sock"


class SocketTransport:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or _default_socket_path()
        self._stdout_handshake_sent = False
        self._socket_handshake_sent = False
        self._step = 0

        if os.path.exists(self.path):
            os.unlink(self.path)

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.path)
        self._server.listen(1)

        self._send_stdout_handshake()

        atexit.register(self.cleanup)
        prev = signal.getsignal(signal.SIGTERM)

        def _on_sigterm(signo: int, frame: types.FrameType | None) -> None:
            self.cleanup()
            if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
                prev(signo, frame)
            sys.exit(0)

        signal.signal(signal.SIGTERM, _on_sigterm)

    def cleanup(self) -> None:
        with contextlib.suppress(Exception):
            self._server.close()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.path)

    def _send_stdout_handshake(self) -> None:
        if self._stdout_handshake_sent:
            return
        self._stdout_handshake_sent = True
        payload = self._handshake_payload()
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _handshake_payload(self) -> dict[str, Any]:
        from importlib.metadata import version

        return {
            "kind": "handshake",
            "protocol": "inquirer-ai",
            "version": version("inquirer-ai"),
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
                    line = rfile.readline()
                    if not line or not line.strip():
                        break

                    line = line.strip()

                    try:
                        raw_parsed: Any = json.loads(line)
                    except json.JSONDecodeError:
                        retries_used += 1
                        msg = f"Invalid JSON: {line}"
                        if retries_used >= _MAX_RETRIES:
                            self._write(wfile, {"kind": "error", "message": msg})
                            raise ValidationError(msg) from None
                        self._write(wfile, {"kind": "validation_error", "message": msg})
                        continue

                    if _is_json_dict(raw_parsed) and raw_parsed.get("kind") == "handshake_ack":
                        line = rfile.readline()
                        if not line or not line.strip():
                            break
                        line = line.strip()
                        try:
                            raw_parsed = json.loads(line)
                        except json.JSONDecodeError:
                            retries_used += 1
                            msg = f"Invalid JSON: {line}"
                            if retries_used >= _MAX_RETRIES:
                                self._write(wfile, {"kind": "error", "message": msg})
                                raise ValidationError(msg) from None
                            self._write(wfile, {"kind": "validation_error", "message": msg})
                            continue

                    if not _is_json_dict(raw_parsed) or "answer" not in raw_parsed:
                        retries_used += 1
                        msg = 'Response must be a JSON object with an "answer" key'
                        if retries_used >= _MAX_RETRIES:
                            self._write(wfile, {"kind": "error", "message": msg})
                            raise ValidationError(msg)
                        self._write(wfile, {"kind": "validation_error", "message": msg})
                        continue

                    answer: Any = raw_parsed["answer"]

                    try:
                        result = validate(answer)
                    except ValidationError as e:
                        retries_used += 1
                        if retries_used >= _MAX_RETRIES:
                            self._write(wfile, {"kind": "error", "message": str(e)})
                            raise
                        self._write(wfile, {"kind": "validation_error", "message": str(e)})
                        continue

                    if user_validate:
                        try:
                            error = user_validate(result)
                        except ValidationError as e:
                            error = str(e)
                        if error:
                            retries_used += 1
                            if retries_used >= _MAX_RETRIES:
                                self._write(wfile, {"kind": "error", "message": error})
                                raise ValidationError(error)
                            self._write(wfile, {"kind": "validation_error", "message": error})
                            continue

                    if filter_fn:
                        result = filter_fn(result)
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

    env_mode = os.environ.get("INQUIRER_AI_MODE", "").lower()
    if env_mode == "human":
        return None
    if sys.platform == "win32":
        return None
    if os.environ.get("INQUIRER_AI_TRANSPORT", "").lower() == "stdio":
        return None

    path = os.environ.get("INQUIRER_AI_SOCKET")
    if path:
        _transport = SocketTransport(path)
        return _transport

    from inquirer_ai.mode import is_agent_mode

    if is_agent_mode():
        _transport = SocketTransport()
        return _transport

    return None


def reset_socket_transport() -> None:
    global _transport, _transport_checked
    if _transport is not None:
        _transport.cleanup()
        _transport = None
    _transport_checked = False
