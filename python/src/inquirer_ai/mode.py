from __future__ import annotations

import os
import sys


def is_agent_mode() -> bool:
    env = os.environ.get("INQUIRER_AI_MODE", "").lower()
    if env == "agent":
        return True
    if env == "human":
        return False
    if os.environ.get("INQUIRER_AI_SOCKET"):
        return True
    return not sys.stdin.isatty()


def is_socket_mode() -> bool:
    if os.environ.get("INQUIRER_AI_MODE", "").lower() == "human":
        return False
    return bool(os.environ.get("INQUIRER_AI_SOCKET"))
