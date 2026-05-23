"""Static type inference tests — verified by pyright, not executed at runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import assert_type

    from inquirer_ai import Choice, checkbox, confirm, select, text

    def check_text_returns_str() -> None:
        result = text("Name")
        assert_type(result, str)

    def check_confirm_returns_bool() -> None:
        result = confirm("OK?")
        assert_type(result, bool)

    def check_select_str_choices_returns_str() -> None:
        result = select("Pick", choices=["a", "b", "c"])
        assert_type(result, str)

    def check_select_typed_choice_returns_value_type() -> None:
        result = select("Pick", choices=[Choice("A", 1), Choice("B", 2)])
        assert_type(result, int)

    def check_checkbox_str_choices_returns_list_str() -> None:
        result = checkbox("Pick", choices=["a", "b", "c"])
        assert_type(result, list[str])

    def check_checkbox_typed_choice_returns_list_value_type() -> None:
        result = checkbox("Pick", choices=[Choice("A", 1), Choice("B", 2)])
        assert_type(result, list[int])
