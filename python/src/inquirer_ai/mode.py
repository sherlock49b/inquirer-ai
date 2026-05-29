from __future__ import annotations

import os
import sys


def _env_eq(name: str, expected: str) -> bool:
    return os.environ.get(name, "").lower() == expected


def is_human_mode() -> bool:
    return _env_eq("INQUIRER_AI_MODE", "human")


def is_socket_requested() -> bool:
    if os.environ.get("INQUIRER_AI_SOCKET", ""):
        return True
    return _env_eq("INQUIRER_AI_MODE", "agent")


def is_agent_mode() -> bool:
    if is_human_mode():
        return False
    if is_socket_requested():
        return True
    return not sys.stdin.isatty()
