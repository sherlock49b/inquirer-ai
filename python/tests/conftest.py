import io
import json

import pytest

import inquirer_ai.prompts.base as _base
import inquirer_ai.socket_transport as _sock


@pytest.fixture(autouse=True)
def _reset_agent_state():
    _base._reset_agent_handshake()
    _sock.reset_socket_transport()
    # Prevent in-process tests from auto-creating sockets.
    # Subprocess-based socket tests run in separate processes and are unaffected.
    _sock._transport_checked = True
    yield
    _base._reset_agent_handshake()
    _sock.reset_socket_transport()


def parse_prompt_from_stdout(stdout: io.StringIO) -> dict[str, object]:
    for line in stdout.getvalue().strip().splitlines():
        parsed = json.loads(line)
        if "type" in parsed and parsed.get("kind") == "prompt":
            return parsed
    raise AssertionError("No prompt line found in stdout")
