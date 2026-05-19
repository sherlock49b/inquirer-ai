from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Choice:
    name: str
    value: Any

    @classmethod
    def from_raw(cls, raw: str | dict[str, Any] | Choice) -> Choice:
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return cls(name=raw, value=raw)
        if isinstance(raw, dict):
            name = raw.get("name", str(raw.get("value", "")))
            value = raw.get("value", name)
            return cls(name=name, value=value)
        raise TypeError(f"Cannot convert {type(raw).__name__} to Choice")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value}
