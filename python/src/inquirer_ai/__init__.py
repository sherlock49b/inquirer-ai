from collections.abc import Callable
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


def text(
    message: str,
    *,
    default: str | None = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> str:
    return TextPrompt(message, default=default, validate=validate, filter=filter).execute()


def confirm(
    message: str,
    *,
    default: bool = False,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> bool:
    return ConfirmPrompt(message, default=default, validate=validate, filter=filter).execute()


def select(
    message: str,
    *,
    choices: list[str | dict[str, Any] | Choice],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return SelectPrompt(message, choices=choices, default=default, validate=validate, filter=filter).execute()


def checkbox(
    message: str,
    *,
    choices: list[str | dict[str, Any] | Choice],
    default: list[Any] | None = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> list[Any]:
    return CheckboxPrompt(message, choices=choices, default=default, validate=validate, filter=filter).execute()


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
