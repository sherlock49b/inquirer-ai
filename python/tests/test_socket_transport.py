"""Tests for Unix socket transport."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from typing import Any

PYTHON = sys.executable


def _wait_for_socket(path: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return
        time.sleep(0.05)
    raise TimeoutError(f"Socket {path} not created within {timeout}s")


def _connect(path: str) -> tuple[socket.socket, Any, Any]:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.settimeout(5)
    return s, s.makefile("r"), s.makefile("w")


def _read_until_prompt(rfile: Any) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    while True:
        line = rfile.readline().strip()
        if not line:
            break
        parsed = json.loads(line)
        messages.append(parsed)
        if parsed.get("kind") == "prompt":
            break
    return messages


def _send_answer(wfile: Any, rfile: Any, answer: Any) -> dict[str, Any]:
    wfile.write(json.dumps({"answer": answer}) + "\n")
    wfile.flush()
    resp = rfile.readline().strip()
    return json.loads(resp)


def _close(s: Any, rfile: Any, wfile: Any) -> None:
    for f in (rfile, wfile):
        with contextlib.suppress(Exception):
            f.close()
    with contextlib.suppress(Exception):
        s.close()


SCRIPT_TEXT = """
import inquirer_ai
name = inquirer_ai.text("Name?")
import sys; print(f"RESULT:{name}", file=sys.stderr, flush=True)
"""

SCRIPT_SELECT = """
import inquirer_ai
lang = inquirer_ai.select("Language?", choices=["Python", "Go", "Rust"])
import sys; print(f"RESULT:{lang}", file=sys.stderr, flush=True)
"""

SCRIPT_NUMBER = """
import inquirer_ai
port = inquirer_ai.number("Port?", min=1024, max=65535)
import sys; print(f"RESULT:{port}", file=sys.stderr, flush=True)
"""

SCRIPT_MULTI = """
import inquirer_ai
name = inquirer_ai.text("Name?")
ok = inquirer_ai.confirm("Sure?", default=True)
import sys; print(f"RESULT:{name},{ok}", file=sys.stderr, flush=True)
"""

SCRIPT_VALIDATE = """
import inquirer_ai
email = inquirer_ai.text("Email?", validate=lambda v: "@" in v or "must contain @")
import sys; print(f"RESULT:{email}", file=sys.stderr, flush=True)
"""


def _run_script(script: str, sock_path: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["INQUIRER_AI_SOCKET"] = sock_path
    env.pop("INQUIRER_AI_MODE", None)
    return subprocess.Popen(
        [PYTHON, "-c", script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _read_stdout_handshake(proc: subprocess.Popen, timeout: float = 5.0) -> dict[str, Any]:
    """Read the handshake line from the process stdout."""
    import select as sel

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = sel.select([proc.stdout], [], [], 0.1)  # type: ignore
        if ready:
            line = proc.stdout.readline().decode().strip()  # type: ignore
            if line:
                return json.loads(line)
    raise TimeoutError("No handshake on stdout")


class TestSocketTransport:
    def test_basic_text_prompt(self, tmp_path):
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            msgs = _read_until_prompt(rf)
            assert msgs[0]["kind"] == "handshake"
            assert msgs[0]["protocol"] == "inquirer-ai"
            assert msgs[0]["socket"] == sock_path
            assert msgs[1]["kind"] == "prompt"
            assert msgs[1]["type"] == "input"
            assert msgs[1]["message"] == "Name?"

            resp = _send_answer(wf, rf, "Alice")
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:Alice" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_select_prompt(self, tmp_path):
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_SELECT, sock_path)
        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            msgs = _read_until_prompt(rf)
            prompt = msgs[-1]
            assert prompt["type"] == "select"
            assert len(prompt["choices"]) == 3

            resp = _send_answer(wf, rf, "Go")
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:Go" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_peek_then_answer(self, tmp_path):
        """Read-only connection (peek) should re-queue the prompt."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            s1, rf1, wf1 = _connect(sock_path)
            msgs1 = _read_until_prompt(rf1)
            assert msgs1[-1]["kind"] == "prompt"
            _close(s1, rf1, wf1)

            s2, rf2, wf2 = _connect(sock_path)
            msgs2 = _read_until_prompt(rf2)
            assert msgs2[0]["kind"] == "prompt"
            assert msgs2[0]["message"] == "Name?"

            resp = _send_answer(wf2, rf2, "Bob")
            assert resp["status"] == "accepted"
            _close(s2, rf2, wf2)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:Bob" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_validation_retry_same_connection(self, tmp_path):
        """Invalid answer gets validation_error, retry on same connection."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_NUMBER, sock_path)
        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)

            resp = _send_answer(wf, rf, 80)
            assert resp["kind"] == "validation_error"
            assert "1024" in resp["message"]

            resp = _send_answer(wf, rf, 8080)
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:8080" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_user_validation_retry(self, tmp_path):
        """User-provided validator errors also trigger retry."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_VALIDATE, sock_path)
        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)

            resp = _send_answer(wf, rf, "invalid")
            assert resp["kind"] == "validation_error"
            assert "@" in resp["message"]

            resp = _send_answer(wf, rf, "test@example.com")
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:test@example.com" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_multi_prompt_sequence(self, tmp_path):
        """Multiple prompts in sequence, each on its own connection."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_MULTI, sock_path)
        try:
            _wait_for_socket(sock_path)

            s1, rf1, wf1 = _connect(sock_path)
            msgs = _read_until_prompt(rf1)
            assert msgs[-1]["type"] == "input"
            assert msgs[-1]["step"] == 1
            resp = _send_answer(wf1, rf1, "Charlie")
            assert resp["status"] == "accepted"
            _close(s1, rf1, wf1)

            s2, rf2, wf2 = _connect(sock_path)
            msgs = _read_until_prompt(rf2)
            assert msgs[0]["type"] == "confirm"
            assert msgs[0]["step"] == 2
            resp = _send_answer(wf2, rf2, False)
            assert resp["status"] == "accepted"
            _close(s2, rf2, wf2)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:Charlie,False" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_handshake_on_stdout_with_socket_path(self, tmp_path):
        """Handshake is written to stdout with socket field for agent discovery."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            handshake = _read_stdout_handshake(proc)
            assert handshake["kind"] == "handshake"
            assert handshake["protocol"] == "inquirer-ai"
            assert handshake["socket"] == sock_path

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)
            _send_answer(wf, rf, "done")
            _close(s, rf, wf)

            proc.wait(timeout=5)
        finally:
            proc.kill()
            proc.wait()

    def test_handshake_only_on_first_socket_connection(self, tmp_path):
        """Socket handshake is sent only on the first connection."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_MULTI, sock_path)
        try:
            _wait_for_socket(sock_path)

            s1, rf1, wf1 = _connect(sock_path)
            msgs1 = _read_until_prompt(rf1)
            assert len(msgs1) == 2
            assert msgs1[0]["kind"] == "handshake"
            assert msgs1[1]["kind"] == "prompt"
            _send_answer(wf1, rf1, "test")
            _close(s1, rf1, wf1)

            s2, rf2, wf2 = _connect(sock_path)
            msgs2 = _read_until_prompt(rf2)
            assert len(msgs2) == 1
            assert msgs2[0]["kind"] == "prompt"
            _send_answer(wf2, rf2, True)
            _close(s2, rf2, wf2)

            proc.wait(timeout=5)
        finally:
            proc.kill()
            proc.wait()

    def test_socket_cleanup_on_exit(self, tmp_path):
        """Socket file is removed when program exits normally."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)
            assert os.path.exists(sock_path)

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)
            _send_answer(wf, rf, "done")
            _close(s, rf, wf)

            proc.wait(timeout=5)
            time.sleep(0.2)
            assert not os.path.exists(sock_path)
        finally:
            proc.kill()
            proc.wait()

    def test_auto_socket_in_agent_mode(self, tmp_path):
        """Agent mode auto-creates socket without INQUIRER_AI_SOCKET."""
        script = """
import inquirer_ai
name = inquirer_ai.text("Name?")
import sys; print(f"RESULT:{name}", file=sys.stderr, flush=True)
"""
        env = os.environ.copy()
        env["INQUIRER_AI_MODE"] = "agent"
        env.pop("INQUIRER_AI_SOCKET", None)
        proc = subprocess.Popen(
            [PYTHON, "-c", script],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            handshake = _read_stdout_handshake(proc)
            assert handshake["kind"] == "handshake"
            assert "socket" in handshake
            sock_path = handshake["socket"]
            assert os.path.exists(sock_path)

            s, rf, wf = _connect(sock_path)
            msgs = _read_until_prompt(rf)
            assert msgs[-1]["kind"] == "prompt"
            resp = _send_answer(wf, rf, "auto-test")
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:auto-test" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_human_mode_overrides_socket(self, tmp_path):
        """INQUIRER_AI_MODE=human should ignore INQUIRER_AI_SOCKET."""
        sock_path = str(tmp_path / "test.sock")
        env = os.environ.copy()
        env["INQUIRER_AI_SOCKET"] = sock_path
        env["INQUIRER_AI_MODE"] = "human"
        proc = subprocess.Popen(
            [PYTHON, "-c", "from inquirer_ai.mode import is_socket_mode; print(is_socket_mode())"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.wait(timeout=5)
        stdout = proc.stdout.read().decode().strip()  # type: ignore
        assert stdout == "False"

    # ------------------------------------------------------------------ #
    # Lifecycle edge-case tests
    # ------------------------------------------------------------------ #

    def test_rapid_reconnection(self, tmp_path):
        """Close and immediately reconnect. No stale state carried over."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            # Connect, read prompt, disconnect immediately (peek)
            s1, rf1, wf1 = _connect(sock_path)
            _read_until_prompt(rf1)
            _close(s1, rf1, wf1)

            # Immediately reconnect — no sleep between
            s2, rf2, wf2 = _connect(sock_path)
            msgs = _read_until_prompt(rf2)
            assert msgs[0]["kind"] == "prompt"
            assert msgs[0]["message"] == "Name?"

            resp = _send_answer(wf2, rf2, "rapid")
            assert resp["status"] == "accepted"
            _close(s2, rf2, wf2)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:rapid" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_partial_message_no_newline(self, tmp_path):
        """Send incomplete JSON (no trailing newline). Server waits for newline;
        completing the line later with valid JSON should succeed."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)

            # Send partial — no newline
            wf.write('{"answer": "part')
            wf.flush()

            # Small delay then complete the line
            time.sleep(0.1)
            wf.write('ial"}\n')
            wf.flush()

            resp_line = rf.readline().strip()
            resp = json.loads(resp_line)
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:partial" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_multiple_clients_second_after_first(self, tmp_path):
        """Two sequential connections for a single prompt. First peeks, second answers."""
        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)

            # Client 1: connect, read prompt, disconnect (peek)
            s1, rf1, wf1 = _connect(sock_path)
            msgs1 = _read_until_prompt(rf1)
            assert msgs1[-1]["kind"] == "prompt"
            _close(s1, rf1, wf1)

            # Client 2: connect, read re-queued prompt, answer
            s2, rf2, wf2 = _connect(sock_path)
            msgs2 = _read_until_prompt(rf2)
            assert msgs2[0]["kind"] == "prompt"
            assert msgs2[0]["message"] == "Name?"

            resp = _send_answer(wf2, rf2, "client2")
            assert resp["status"] == "accepted"
            _close(s2, rf2, wf2)

            proc.wait(timeout=5)
            stderr = proc.stderr.read().decode()  # type: ignore
            assert "RESULT:client2" in stderr
        finally:
            proc.kill()
            proc.wait()

    def test_socket_cleanup_on_sigterm(self, tmp_path):
        """Socket file is removed when process receives SIGTERM."""
        import signal as sig

        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        try:
            _wait_for_socket(sock_path)
            assert os.path.exists(sock_path)

            # Send SIGTERM instead of answering
            proc.send_signal(sig.SIGTERM)
            proc.wait(timeout=5)

            time.sleep(0.2)
            assert not os.path.exists(sock_path), "socket file should be removed after SIGTERM"
        finally:
            proc.kill()
            proc.wait()

    def test_large_payload(self, tmp_path):
        """Send a very large answer (> 100 KB). Verify it is accepted without error."""
        import threading

        sock_path = str(tmp_path / "test.sock")
        proc = _run_script(SCRIPT_TEXT, sock_path)
        stderr_chunks: list[bytes] = []

        # Read stderr in a background thread to prevent pipe buffer deadlock
        def _drain_stderr():
            while True:
                chunk = proc.stderr.read(4096)  # type: ignore
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()

        try:
            _wait_for_socket(sock_path)

            s, rf, wf = _connect(sock_path)
            _read_until_prompt(rf)

            # Build a 100 KB+ string
            large_value = "x" * (100 * 1024)
            resp = _send_answer(wf, rf, large_value)
            assert resp["status"] == "accepted"
            _close(s, rf, wf)

            proc.wait(timeout=15)
            t.join(timeout=5)
            stderr = b"".join(stderr_chunks).decode()
            assert "RESULT:" in stderr
            # The result should contain the large payload (or at least start with the right chars)
            assert large_value[:20] in stderr
        finally:
            proc.kill()
            proc.wait()
