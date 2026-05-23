import io
import json

import pytest

import inquirer_ai.prompts.base as _base


@pytest.fixture(autouse=True)
def _reset_agent_handshake():
    _base._reset_agent_handshake()
    yield
    _base._reset_agent_handshake()


def parse_prompt_from_stdout(stdout: io.StringIO) -> dict[str, object]:
    for line in stdout.getvalue().strip().splitlines():
        parsed = json.loads(line)
        if "type" in parsed and parsed.get("kind") == "prompt":
            return parsed
    raise AssertionError("No prompt line found in stdout")
