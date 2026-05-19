from inquirer_ai.choice import Choice
from inquirer_ai.core import prompt
from inquirer_ai.exceptions import InquirerAIError, PromptAbortedError, ValidationError
from inquirer_ai.mode import is_agent_mode
from inquirer_ai.prompts.checkbox import CheckboxPrompt
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.select import SelectPrompt
from inquirer_ai.prompts.text import TextPrompt


def text(message: str, **kwargs) -> str:
    return TextPrompt(message, **kwargs).execute()


def confirm(message: str, **kwargs) -> bool:
    return ConfirmPrompt(message, **kwargs).execute()


def select(message: str, **kwargs):
    return SelectPrompt(message, **kwargs).execute()


def checkbox(message: str, **kwargs) -> list:
    return CheckboxPrompt(message, **kwargs).execute()


__all__ = [
    "text",
    "confirm",
    "select",
    "checkbox",
    "prompt",
    "is_agent_mode",
    "Choice",
    "TextPrompt",
    "ConfirmPrompt",
    "SelectPrompt",
    "CheckboxPrompt",
    "InquirerAIError",
    "PromptAbortedError",
    "ValidationError",
]
