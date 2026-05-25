import sys

from inquirer_ai.compat import questionary

sys.modules["questionary"] = questionary

from .teamcz import TeamCz  # noqa: E402, F401
