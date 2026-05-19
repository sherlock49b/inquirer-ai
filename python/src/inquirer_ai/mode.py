from __future__ import annotations

import os
import sys


def is_agent_mode() -> bool:
    env = os.environ.get("INQUIRER_AI_MODE", "").lower()
    if env == "agent":
        return True
    if env == "human":
        return False
    return not sys.stdin.isatty()
