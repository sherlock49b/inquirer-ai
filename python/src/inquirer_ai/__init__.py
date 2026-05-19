from typing import Any

from inquirer_ai.choice import Choice
from inquirer_ai.core import Question, prompt
from inquirer_ai.exceptions import InquirerAIError, PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode
from inquirer_ai.theme import Theme, get_theme, set_theme
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


def text(message: str, *, default: str | None = None) -> str:
    return TextPrompt(message, default=default).execute()


def confirm(message: str, *, default: bool = False) -> bool:
    return ConfirmPrompt(message, default=default).execute()


def select(
    message: str,
    *,
    choices: list[str | dict[str, Any] | Choice],
    default: Any = None,
) -> Any:
    return SelectPrompt(message, choices=choices, default=default).execute()


def checkbox(
    message: str,
    *,
    choices: list[str | dict[str, Any] | Choice],
    default: list[Any] | None = None,
) -> list[Any]:
    return CheckboxPrompt(message, choices=choices, default=default).execute()


__all__ = [
    "text",
    "confirm",
    "select",
    "checkbox",
    "prompt",
    "Question",
    "is_agent_mode",
    "Choice",
    "TextPrompt",
    "ConfirmPrompt",
    "SelectPrompt",
    "CheckboxPrompt",
    "Theme",
    "get_theme",
    "set_theme",
    "InquirerAIError",
    "PromptAbortedError",
    "ValidationError",
]
