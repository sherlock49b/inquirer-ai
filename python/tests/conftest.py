import io
import json

import pytest

import inquirer_ai.prompts.base as _base


@pytest.fixture(autouse=True)
def _reset_agent_handshake():
    _base._agent_handshake_sent = False
    yield
    _base._agent_handshake_sent = False


def parse_prompt_from_stdout(stdout: io.StringIO) -> dict[str, object]:
    for line in stdout.getvalue().strip().splitlines():
        parsed = json.loads(line)
        if "type" in parsed:
            return parsed
    raise AssertionError("No prompt line found in stdout")
