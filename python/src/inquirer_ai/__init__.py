from collections.abc import Callable, Sequence
from importlib.metadata import version
from typing import Any, TypeVar, overload

from inquirer_ai.choice import Choice
from inquirer_ai.core import Question, prompt
from inquirer_ai.exceptions import InquirerAIError, PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt
from inquirer_ai.theme import Theme, get_theme, set_theme

__version__ = version("inquirer-ai")

V = TypeVar("V")


def text(
    message: str,
    *,
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return TextPrompt(message, default=default, validate=validate, filter=filter).execute()


def confirm(
    message: str,
    *,
    default: bool = False,
    validate: Callable[[bool], bool | str | None] | None = None,
    filter: Callable[[bool], bool] | None = None,
) -> bool:
    return ConfirmPrompt(message, default=default, validate=validate, filter=filter).execute()


@overload
def select(
    message: str,
    *,
    choices: Sequence[str],
    default: str | None = ...,
    page_size: int = ...,
    validate: Callable[[str], bool | str | None] | None = ...,
    filter: Callable[[str], str] | None = ...,
) -> str: ...
@overload
def select(
    message: str,
    *,
    choices: Sequence[Choice[V]],
    default: V | None = ...,
    page_size: int = ...,
    validate: Callable[[V], bool | str | None] | None = ...,
    filter: Callable[[V], V] | None = ...,
) -> V: ...
@overload
def select(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = ...,
    page_size: int = ...,
    validate: Callable[[Any], bool | str | None] | None = ...,
    filter: Callable[[Any], Any] | None = ...,
) -> Any: ...
def select(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return SelectPrompt(
        message, choices=list(choices), default=default, page_size=page_size, validate=validate, filter=filter
    ).execute()


@overload
def checkbox(
    message: str,
    *,
    choices: Sequence[str],
    default: list[str] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[str]], bool | str | None] | None = ...,
    filter: Callable[[list[str]], list[str]] | None = ...,
) -> list[str]: ...
@overload
def checkbox(
    message: str,
    *,
    choices: Sequence[Choice[V]],
    default: list[V] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[V]], bool | str | None] | None = ...,
    filter: Callable[[list[V]], list[V]] | None = ...,
) -> list[V]: ...
@overload
def checkbox(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: list[Any] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[Any]], bool | str | None] | None = ...,
    filter: Callable[[list[Any]], list[Any]] | None = ...,
) -> list[Any]: ...
def checkbox(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: list[Any] | None = None,
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> list[Any]:
    return CheckboxPrompt(
        message, choices=list(choices), default=default, page_size=page_size, validate=validate, filter=filter
    ).execute()


__all__ = [
    "CheckboxPrompt",
    "Choice",
    "ConfirmPrompt",
    "InquirerAIError",
    "PromptAbortedError",
    "Question",
    "SelectPrompt",
    "TextPrompt",
    "Theme",
    "ValidationError",
    "__version__",
    "checkbox",
    "confirm",
    "get_theme",
    "is_agent_mode",
    "prompt",
    "select",
    "set_theme",
    "text",
]
