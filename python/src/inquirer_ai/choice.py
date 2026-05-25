from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, overload

from inquirer_ai.exceptions import InvalidChoiceError

V = TypeVar("V")


@dataclass
class Choice(Generic[V]):
    name: str
    value: V
    disabled: bool | str = False
    short: str | None = None
    description: str | None = None

    @overload
    @classmethod
    def from_raw(cls, raw: str) -> Choice[str]: ...
    @overload
    @classmethod
    def from_raw(cls, raw: dict[str, Any] | Choice[Any]) -> Choice[Any]: ...
    @classmethod
    def from_raw(cls, raw: str | dict[str, Any] | Choice[Any]) -> Choice[Any]:
        if isinstance(raw, Choice):
            return raw
        if isinstance(raw, str):
            return Choice(name=raw, value=raw)
        # Runtime guard for callers passing invalid types via type: ignore.
        # Use type() instead of isinstance() to avoid pyright narrowing issues
        # since the static type is already dict[str, Any] at this point.
        if type(raw) is not dict:
            raise InvalidChoiceError(f"Cannot convert {type(raw).__name__} to Choice")
        if "name" not in raw and "value" not in raw:
            raise InvalidChoiceError("Choice dict must have at least 'name' or 'value'")
        name: str = raw.get("name", str(raw.get("value", "")))
        value: Any = raw.get("value", name)
        disabled: bool | str = raw.get("disabled", False)
        short: str | None = raw.get("short")
        description: str | None = raw.get("description")
        return Choice(name=name, value=value, disabled=disabled, short=short, description=description)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "value": self.value}
        if self.disabled:
            d["disabled"] = self.disabled
        if self.short is not None:
            d["short"] = self.short
        if self.description is not None:
            d["description"] = self.description
        return d


@dataclass
class Separator:
    text: str = field(default="────────")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "separator", "text": self.text}


ChoiceItem = Choice[Any] | Separator
RawChoice = str | dict[str, Any] | Choice[Any] | Separator


def parse_choice(raw: RawChoice) -> ChoiceItem:
    if isinstance(raw, Separator):
        return raw
    return Choice.from_raw(raw)
