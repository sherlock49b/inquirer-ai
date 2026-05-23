from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, overload

V = TypeVar("V")


@dataclass
class Choice(Generic[V]):
    name: str
    value: V

    @overload
    @classmethod
    def from_raw(cls, raw: str) -> Choice[str]: ...
    @overload
    @classmethod
    def from_raw(cls, raw: Choice[V]) -> Choice[V]: ...
    @overload
    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Choice[Any]: ...
    @classmethod
    def from_raw(cls, raw: str | dict[str, Any] | Choice[Any]) -> Choice[Any]:
        if isinstance(raw, Choice):
            return raw
        if isinstance(raw, str):
            return Choice(name=raw, value=raw)
        if isinstance(raw, dict):
            name = raw.get("name", str(raw.get("value", "")))
            value = raw.get("value", name)
            return Choice(name=name, value=value)
        raise TypeError(f"Cannot convert {type(raw).__name__} to Choice")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value}
