from collections.abc import Callable, Sequence
from importlib.metadata import version
from typing import Any, TypeVar, overload

from inquirer_ai.choice import Choice, RawChoice, Separator
from inquirer_ai.core import Question, prompt
from inquirer_ai.exceptions import EditorError, InquirerAIError, InvalidChoiceError, PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode
from inquirer_ai.prompts.autocomplete import AutocompletePrompt
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.editor import EditorPrompt
from inquirer_ai.prompts.expand import ExpandChoice, ExpandPrompt
from inquirer_ai.prompts.number import NumberPrompt
from inquirer_ai.prompts.password import PasswordPrompt
from inquirer_ai.prompts.rawlist import RawlistPrompt
from inquirer_ai.prompts.search import SearchPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt
from inquirer_ai.theme import Theme, get_theme, set_theme

__version__ = version("inquirer-ai")

V = TypeVar("V")


def autocomplete(
    message: str,
    *,
    choices: list[str],
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return AutocompletePrompt(message, choices=choices, default=default, validate=validate, filter=filter).execute()


def text(
    message: str,
    *,
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
    transformer: Callable[[str], str] | None = None,
) -> str:
    return TextPrompt(message, default=default, validate=validate, filter=filter, transformer=transformer).execute()


def confirm(
    message: str,
    *,
    default: bool = False,
    validate: Callable[[bool], bool | str | None] | None = None,
    filter: Callable[[bool], bool] | None = None,
    transformer: Callable[[bool], str] | None = None,
) -> bool:
    return ConfirmPrompt(message, default=default, validate=validate, filter=filter, transformer=transformer).execute()


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
    validate: Callable[[list[Any]], bool | str | None] | None = None,
    filter: Callable[[list[Any]], list[Any]] | None = None,
) -> list[Any]:
    return CheckboxPrompt(
        message, choices=list(choices), default=default, page_size=page_size, validate=validate, filter=filter
    ).execute()


def editor(
    message: str,
    *,
    default: str | None = None,
    postfix: str = ".txt",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return EditorPrompt(message, default=default, postfix=postfix, validate=validate, filter=filter).execute()


def search(
    message: str,
    *,
    source: Callable[[str], list[RawChoice]],
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return SearchPrompt(message, source=source, page_size=page_size, validate=validate, filter=filter).execute()


def rawlist(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return RawlistPrompt(message, choices=list(choices), default=default, validate=validate, filter=filter).execute()


def expand(
    message: str,
    *,
    choices: list[dict[str, Any] | ExpandChoice],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return ExpandPrompt(message, choices=choices, default=default, validate=validate, filter=filter).execute()


def password(
    message: str,
    *,
    mask: str | None = "*",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return PasswordPrompt(message, mask=mask, validate=validate, filter=filter).execute()


def number(
    message: str,
    *,
    default: int | float | None = None,
    min: int | float | None = None,
    max: int | float | None = None,
    float_allowed: bool = True,
    validate: Callable[[int | float], bool | str | None] | None = None,
    filter: Callable[[int | float], int | float] | None = None,
) -> int | float:
    return NumberPrompt(
        message, default=default, min=min, max=max, float_allowed=float_allowed, validate=validate, filter=filter
    ).execute()


# --- Async convenience functions ---


async def autocomplete_async(
    message: str,
    *,
    choices: list[str],
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return await AutocompletePrompt(
        message, choices=choices, default=default, validate=validate, filter=filter
    ).execute_async()


async def text_async(
    message: str,
    *,
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
    transformer: Callable[[str], str] | None = None,
) -> str:
    return await TextPrompt(
        message, default=default, validate=validate, filter=filter, transformer=transformer
    ).execute_async()


async def confirm_async(
    message: str,
    *,
    default: bool = False,
    validate: Callable[[bool], bool | str | None] | None = None,
    filter: Callable[[bool], bool] | None = None,
    transformer: Callable[[bool], str] | None = None,
) -> bool:
    return await ConfirmPrompt(
        message, default=default, validate=validate, filter=filter, transformer=transformer
    ).execute_async()


@overload
async def select_async(
    message: str,
    *,
    choices: Sequence[str],
    default: str | None = ...,
    page_size: int = ...,
    validate: Callable[[str], bool | str | None] | None = ...,
    filter: Callable[[str], str] | None = ...,
) -> str: ...
@overload
async def select_async(
    message: str,
    *,
    choices: Sequence[Choice[V]],
    default: V | None = ...,
    page_size: int = ...,
    validate: Callable[[V], bool | str | None] | None = ...,
    filter: Callable[[V], V] | None = ...,
) -> V: ...
@overload
async def select_async(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = ...,
    page_size: int = ...,
    validate: Callable[[Any], bool | str | None] | None = ...,
    filter: Callable[[Any], Any] | None = ...,
) -> Any: ...
async def select_async(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return await SelectPrompt(
        message, choices=list(choices), default=default, page_size=page_size, validate=validate, filter=filter
    ).execute_async()


@overload
async def checkbox_async(
    message: str,
    *,
    choices: Sequence[str],
    default: list[str] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[str]], bool | str | None] | None = ...,
    filter: Callable[[list[str]], list[str]] | None = ...,
) -> list[str]: ...
@overload
async def checkbox_async(
    message: str,
    *,
    choices: Sequence[Choice[V]],
    default: list[V] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[V]], bool | str | None] | None = ...,
    filter: Callable[[list[V]], list[V]] | None = ...,
) -> list[V]: ...
@overload
async def checkbox_async(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: list[Any] | None = ...,
    page_size: int = ...,
    validate: Callable[[list[Any]], bool | str | None] | None = ...,
    filter: Callable[[list[Any]], list[Any]] | None = ...,
) -> list[Any]: ...
async def checkbox_async(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: list[Any] | None = None,
    page_size: int = 10,
    validate: Callable[[list[Any]], bool | str | None] | None = None,
    filter: Callable[[list[Any]], list[Any]] | None = None,
) -> list[Any]:
    return await CheckboxPrompt(
        message, choices=list(choices), default=default, page_size=page_size, validate=validate, filter=filter
    ).execute_async()


async def editor_async(
    message: str,
    *,
    default: str | None = None,
    postfix: str = ".txt",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return await EditorPrompt(
        message, default=default, postfix=postfix, validate=validate, filter=filter
    ).execute_async()


async def search_async(
    message: str,
    *,
    source: Callable[[str], list[RawChoice]],
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return await SearchPrompt(
        message, source=source, page_size=page_size, validate=validate, filter=filter
    ).execute_async()


async def rawlist_async(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return await RawlistPrompt(
        message, choices=list(choices), default=default, validate=validate, filter=filter
    ).execute_async()


async def expand_async(
    message: str,
    *,
    choices: list[dict[str, Any] | ExpandChoice],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any:
    return await ExpandPrompt(
        message, choices=choices, default=default, validate=validate, filter=filter
    ).execute_async()


async def password_async(
    message: str,
    *,
    mask: str | None = "*",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str:
    return await PasswordPrompt(message, mask=mask, validate=validate, filter=filter).execute_async()


async def number_async(
    message: str,
    *,
    default: int | float | None = None,
    min: int | float | None = None,
    max: int | float | None = None,
    float_allowed: bool = True,
    validate: Callable[[int | float], bool | str | None] | None = None,
    filter: Callable[[int | float], int | float] | None = None,
) -> int | float:
    return await NumberPrompt(
        message, default=default, min=min, max=max, float_allowed=float_allowed, validate=validate, filter=filter
    ).execute_async()


__all__ = [
    "AutocompletePrompt",
    "CheckboxPrompt",
    "Choice",
    "ConfirmPrompt",
    "EditorError",
    "EditorPrompt",
    "ExpandChoice",
    "ExpandPrompt",
    "InquirerAIError",
    "InvalidChoiceError",
    "NumberPrompt",
    "PasswordPrompt",
    "PromptAbortedError",
    "Question",
    "RawlistPrompt",
    "SearchPrompt",
    "SelectPrompt",
    "Separator",
    "TextPrompt",
    "Theme",
    "ValidationError",
    "__version__",
    "autocomplete",
    "autocomplete_async",
    "checkbox",
    "checkbox_async",
    "confirm",
    "confirm_async",
    "editor",
    "editor_async",
    "expand",
    "expand_async",
    "get_theme",
    "is_agent_mode",
    "number",
    "number_async",
    "password",
    "password_async",
    "prompt",
    "rawlist",
    "rawlist_async",
    "search",
    "search_async",
    "select",
    "select_async",
    "set_theme",
    "text",
    "text_async",
]
