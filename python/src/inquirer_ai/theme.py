from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

RESET = "\033[0m"


@dataclass(frozen=True)
class Theme:
    # oklch(0.74 0.090 280) - soft lavender for question mark
    question: str = "#9fa4e3"
    # oklch(0.74 0.100 170) - muted teal for success checkmark
    success: str = "#62bfa1"
    # oklch(0.72 0.120 285) - deeper violet for cursor pointer
    pointer: str = "#9c99ec"
    # oklch(0.78 0.080 250) - light periwinkle for focused item
    highlight: str = "#90bbe9"
    # oklch(0.73 0.100 175) - soft teal for checked items
    selected: str = "#59bca4"
    # oklch(0.78 0.060 255) - subtle blue for answer text
    answer: str = "#9db9dd"
    # oklch(0.68 0.120 15) - soft coral for errors
    error: str = "#d77780"
    # oklch(0.62 0.015 280) - cool gray for hints
    muted: str = "#84858f"

    sym_question: str = "?"
    sym_success: str = "✓"
    sym_pointer: str = "❯"
    sym_checked: str = "◉"
    sym_unchecked: str = "◯"

    def ansi(self, hex_color: str) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"\033[38;2;{r};{g};{b}m"

    def pt(self, hex_color: str) -> str:
        return f"fg:{hex_color}"

    def pt_bold(self, hex_color: str) -> str:
        return f"fg:{hex_color} bold"


_theme_var: ContextVar[Theme] = ContextVar("inquirer_ai_theme", default=Theme())  # noqa: B039


def set_theme(theme: Theme) -> None:
    _theme_var.set(theme)


def get_theme() -> Theme:
    return _theme_var.get()
