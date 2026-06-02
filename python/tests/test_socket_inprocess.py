"""In-process tests for the Unix socket transport.

These drive ``SocketTransport.prompt_cycle`` on a worker thread while a client
socket connects from the test (main) thread, exercising the transport code
directly so it counts toward coverage.
"""

from __future__ import annotations

import io
import json
import os
import socket
import stat
import sys
import threading
from typing import Any

import pytest

from inquirer_ai.exceptions import ValidationError
from inquirer_ai.socket_transport import (
    SocketTransport,
    SocketTransportError,
    get_socket_transport,
    reset_socket_transport,
)


@pytest.fixture
def stub_stdout(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    return buf


class _Client:
    def __init__(self, path: str) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.sock.settimeout(5)
        self.rf = self.sock.makefile("r")
        self.wf = self.sock.makefile("w")

    def read_json(self) -> dict[str, Any]:
        line = self.rf.readline().strip()
        return json.loads(line)

    def read_until(self, kind: str) -> dict[str, Any]:
        while True:
            msg = self.read_json()
            if msg.get("kind") == kind or msg.get("status"):
                return msg

    def send(self, obj: Any) -> None:
        self.wf.write(json.dumps(obj) + "\n")
        self.wf.flush()

    def send_raw(self, text: str) -> None:
        self.wf.write(text)
        self.wf.flush()

    def close(self) -> None:
        import contextlib

        for f in (self.rf, self.wf):
            with contextlib.suppress(Exception):
                f.close()
        with contextlib.suppress(Exception):
            self.sock.close()


def _run_cycle(
    transport: SocketTransport,
    payload: dict[str, Any] | None = None,
    validate: Any = None,
    **kw: Any,
) -> tuple[threading.Thread, dict[str, Any]]:
    payload = payload or {"kind": "prompt", "type": "input", "message": "q"}
    validate = validate or (lambda a: str(a) if a is not None else "")
    result: dict[str, Any] = {}

    def run() -> None:
        try:
            result["value"] = transport.prompt_cycle(payload, validate, **kw)
        except BaseException as exc:
            result["error"] = exc

    th = threading.Thread(target=run)
    th.start()
    return th, result


@pytest.fixture
def transport(tmp_path: Any, stub_stdout: io.StringIO):
    path = str(tmp_path / "t.sock")
    t = SocketTransport(path)
    yield t
    reset_socket_transport()
    t.cleanup()


class TestSocketHappyPath:
    def test_handshake_then_accept(self, transport: SocketTransport, stub_stdout: io.StringIO) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        hs = c.read_json()
        assert hs["kind"] == "handshake"
        assert hs["version"]  # comes from the package version, never empty
        prompt = c.read_json()
        assert prompt["kind"] == "prompt"
        assert prompt["step"] == 1
        c.send({"answer": "hello"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "hello"
        # The stdout handshake was written during construction.
        assert json.loads(stub_stdout.getvalue().splitlines()[0])["kind"] == "handshake"

    def test_socket_chmod_0600(self, transport: SocketTransport) -> None:
        mode = stat.S_IMODE(os.lstat(transport.path).st_mode)
        assert mode == 0o600

    def test_handshake_ack_is_consumed(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        c.read_json()  # handshake
        c.read_json()  # prompt
        c.send({"kind": "handshake_ack"})
        c.send({"answer": "after-ack"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "after-ack"

    def test_filter_applied_after_validate(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport, validate=lambda a: str(a), filter_fn=lambda v: v.upper())
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"answer": "abc"})
        c.read_json()
        th.join(timeout=5)
        c.close()
        assert result["value"] == "ABC"


class TestSocketRetryBudget:
    def test_two_invalid_then_valid(self, transport: SocketTransport) -> None:
        def validate(a: Any) -> str:
            if a == "bad":
                raise ValidationError("nope")
            return str(a)

        th, result = _run_cycle(transport, validate=validate)
        c = _Client(transport.path)
        c.read_json()  # handshake
        c.read_json()  # prompt
        c.send({"answer": "bad"})
        assert c.read_json()["kind"] == "validation_error"
        c.send({"answer": "bad"})
        assert c.read_json()["kind"] == "validation_error"
        c.send({"answer": "good"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "good"

    def test_three_invalid_is_fatal_error(self, transport: SocketTransport) -> None:
        def validate(a: Any) -> str:
            raise ValidationError("always bad")

        th, result = _run_cycle(transport, validate=validate)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"answer": "x"})
        assert c.read_json()["kind"] == "validation_error"
        c.send({"answer": "x"})
        assert c.read_json()["kind"] == "validation_error"
        c.send({"answer": "x"})
        assert c.read_json()["kind"] == "error"
        th.join(timeout=5)
        c.close()
        assert isinstance(result.get("error"), ValidationError)

    def test_malformed_json_consumes_retry(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send_raw("not json\n")
        msg = c.read_json()
        assert msg["kind"] == "validation_error"
        assert "Invalid JSON response" in msg["message"]
        c.send({"answer": "recovered"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "recovered"

    def test_missing_answer_field_message(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"not_answer": 1})
        msg = c.read_json()
        assert msg["kind"] == "validation_error"
        assert msg["message"] == 'Answer must be a JSON object with an "answer" field'
        c.send({"answer": "ok"})
        c.read_json()
        th.join(timeout=5)
        c.close()
        assert result["value"] == "ok"

    def test_user_validate_failure_consumes_retry(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(
            transport,
            validate=lambda a: str(a),
            user_validate=lambda v: "too short" if len(v) < 3 else None,
        )
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"answer": "ab"})
        assert c.read_json()["message"] == "too short"
        c.send({"answer": "abcd"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "abcd"

    def test_line_size_cap(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        huge = '{"answer": "' + ("a" * 1_100_000) + '"}\n'
        c.send_raw(huge)
        msg = c.read_json()
        assert msg["kind"] == "validation_error"
        assert "maximum size" in msg["message"]
        c.send({"answer": "small"})
        assert c.read_json()["status"] == "accepted"
        th.join(timeout=5)
        c.close()
        assert result["value"] == "small"


class TestSocketValidatorCrash:
    def test_non_validation_error_reported_then_fatal(self, transport: SocketTransport) -> None:
        def validate(a: Any) -> str:
            raise RuntimeError("boom in validator")

        th, result = _run_cycle(transport, validate=validate)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"answer": "x"})
        msg = c.read_json()
        assert msg["kind"] == "error"
        assert "boom in validator" in msg["message"]
        th.join(timeout=5)
        c.close()
        assert isinstance(result.get("error"), ValidationError)


class TestSocketBrokenPipe:
    def test_accepted_write_failure_does_not_lose_answer(self, transport: SocketTransport) -> None:
        th, result = _run_cycle(transport)
        c = _Client(transport.path)
        c.read_json()
        c.read_json()
        c.send({"answer": "keepme"})
        # Close the client immediately so writing {"status":"accepted"} may
        # hit a broken pipe; the result must still be returned.
        c.close()
        th.join(timeout=5)
        assert result.get("value") == "keepme"


class TestSocketStartupHardening:
    def test_refuses_non_socket_regular_file(self, tmp_path: Any, stub_stdout: io.StringIO) -> None:
        path = tmp_path / "regular.sock"
        path.write_text("not a socket")
        with pytest.raises(SocketTransportError, match="not a socket"):
            SocketTransport(str(path))

    def test_refuses_directory(self, tmp_path: Any, stub_stdout: io.StringIO) -> None:
        path = tmp_path / "adir"
        path.mkdir()
        with pytest.raises(SocketTransportError):
            SocketTransport(str(path))

    def test_stale_socket_is_unlinked(self, tmp_path: Any, stub_stdout: io.StringIO) -> None:
        path = str(tmp_path / "stale.sock")
        # Create a real (stale) socket file at the path, then bind a new one.
        old = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old.bind(path)
        old.close()
        assert os.path.exists(path)
        t = SocketTransport(path)  # should unlink the stale socket and rebind
        try:
            assert stat.S_ISSOCK(os.lstat(path).st_mode)
        finally:
            t.cleanup()

    def test_cleanup_idempotent(self, tmp_path: Any, stub_stdout: io.StringIO) -> None:
        t = SocketTransport(str(tmp_path / "c.sock"))
        t.cleanup()
        assert not os.path.exists(t.path)
        t.cleanup()  # second call is a no-op


class TestGetSocketTransportSelection:
    def test_human_mode_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "human")
        monkeypatch.setenv("INQUIRER_AI_SOCKET", "/tmp/should-not-matter.sock")
        reset_socket_transport()
        try:
            assert get_socket_transport() is None
        finally:
            reset_socket_transport()

    def test_transport_stdio_disables_socket(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setenv("INQUIRER_AI_SOCKET", str(tmp_path / "s.sock"))
        monkeypatch.setenv("INQUIRER_AI_TRANSPORT", "stdio")
        reset_socket_transport()
        try:
            assert get_socket_transport() is None
        finally:
            reset_socket_transport()

    def test_piped_non_tty_without_socket_stays_stdio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A plain piped non-TTY with no MODE/SOCKET must NOT use the socket.
        monkeypatch.delenv("INQUIRER_AI_MODE", raising=False)
        monkeypatch.delenv("INQUIRER_AI_SOCKET", raising=False)
        monkeypatch.delenv("INQUIRER_AI_TRANSPORT", raising=False)
        fake = type("S", (), {"isatty": staticmethod(lambda: False)})()
        monkeypatch.setattr("sys.stdin", fake)
        reset_socket_transport()
        try:
            assert get_socket_transport() is None
        finally:
            reset_socket_transport()

    def test_socket_env_activates_even_on_tty(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("INQUIRER_AI_MODE", raising=False)
        monkeypatch.delenv("INQUIRER_AI_TRANSPORT", raising=False)
        monkeypatch.setenv("INQUIRER_AI_SOCKET", str(tmp_path / "tty.sock"))
        fake = type("S", (), {"isatty": staticmethod(lambda: True)})()
        monkeypatch.setattr("sys.stdin", fake)
        # Avoid the stdout handshake polluting test output.
        monkeypatch.setattr("sys.stdout", io.StringIO())
        reset_socket_transport()
        try:
            t = get_socket_transport()
            assert t is not None
        finally:
            reset_socket_transport()


class TestExplicitPathValidation:
    def _make(self, path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setenv("INQUIRER_AI_SOCKET", path)
        monkeypatch.setattr("sys.stdout", io.StringIO())
        reset_socket_transport()

    def test_relative_path_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._make("relative.sock", monkeypatch)
        try:
            with pytest.raises(SocketTransportError, match="absolute"):
                get_socket_transport()
        finally:
            reset_socket_transport()

    def test_too_long_path_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._make("/tmp/" + "x" * 200 + ".sock", monkeypatch)
        try:
            with pytest.raises(SocketTransportError, match="too long"):
                get_socket_transport()
        finally:
            reset_socket_transport()

    def test_missing_parent_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._make("/nonexistent-dir-xyz/sock", monkeypatch)
        try:
            with pytest.raises(SocketTransportError, match="parent directory"):
                get_socket_transport()
        finally:
            reset_socket_transport()


def teardown_module(_module: Any) -> None:
    reset_socket_transport()
    # Restore a real stdout in case a test left a StringIO around.
    sys.stdout = sys.__stdout__
