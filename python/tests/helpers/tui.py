"""TUI testing helpers for inquirer-ai terminal-mode prompts.

Provides utilities to simulate key sequences and capture results without
a real terminal.  Two strategies are used depending on the prompt type:

* **Simple prompts** (text, confirm, number, password) call
  ``prompt_toolkit.prompt`` (imported as ``pt_prompt``).  We mock that
  function to return pre-defined strings one at a time.

* **Choice-based prompts** (select, checkbox, search) build a
  ``prompt_toolkit.Application`` with ``KeyBindings`` and call
  ``app.run()``.  We intercept the ``Application`` constructor, extract
  the registered key bindings, replay the requested key sequence by
  calling the bound handlers with a lightweight mock event, and return
  whatever ``event.app.exit(result=...)`` received.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Sequence
from typing import Any
from unittest.mock import patch

from prompt_toolkit.keys import Keys

# ---------------------------------------------------------------------------
# ANSI escape-code stripper
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from *text*."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Key constants  (convenience aliases used in test code)
# ---------------------------------------------------------------------------

UP = "up"
DOWN = "down"
ENTER = "enter"
SPACE = "space"
TAB = "tab"
ESCAPE = "escape"


# ---------------------------------------------------------------------------
# Internal: key-name to prompt_toolkit key mapping
# ---------------------------------------------------------------------------

_KEY_MAP: dict[str, tuple[Any, ...]] = {
    "up": (Keys.Up,),
    "down": (Keys.Down,),
    "enter": (Keys.Enter,),  # type: ignore[attr-defined]
    "space": (" ",),
    "tab": (Keys.Tab,),  # type: ignore[attr-defined]
    "escape": (Keys.Escape,),
    "c-c": (Keys.ControlC,),
    "backspace": (Keys.Backspace,),  # type: ignore[attr-defined]
}


def _resolve_key(name: str) -> tuple[Any, ...]:
    """Return the prompt_toolkit key tuple for a symbolic name or character."""
    lower = name.lower()
    if lower in _KEY_MAP:
        return _KEY_MAP[lower]
    # Single printable character  --  prompt_toolkit stores these as the char
    if len(name) == 1:
        return (name,)
    # Try Keys enum directly
    try:
        return (Keys[name],)
    except KeyError:
        raise ValueError(f"Unknown key name: {name!r}") from None


# ---------------------------------------------------------------------------
# _FakeApp / _FakeEvent  --  lightweight stand-ins for prompt_toolkit objects
# ---------------------------------------------------------------------------


class _ExitSentinel(Exception):
    """Raised by ``_FakeApp.exit`` to short-circuit the key-replay loop."""

    def __init__(self, result: Any) -> None:
        self.result = result


class _FakeApp:
    """Mimics the subset of ``prompt_toolkit.Application`` used by handlers."""

    def __init__(self) -> None:
        self.result: Any = None
        self._exited = False

    def exit(self, result: Any = None) -> None:
        self.result = result
        self._exited = True
        raise _ExitSentinel(result)


class _FakeEvent:
    """Mimics ``KeyPressEvent`` well enough for the handlers in choice_base."""

    def __init__(self, app: _FakeApp, data: str = "") -> None:
        self.app = app
        self.data = data


# ---------------------------------------------------------------------------
# Core: simulate_keys  (choice-based prompts)
# ---------------------------------------------------------------------------


def _find_handler(bindings: Any, key_tuple: tuple[Any, ...]) -> Any:
    """Find the first handler whose key tuple matches *key_tuple*."""
    for binding in bindings:
        if binding.keys == key_tuple:
            return binding.handler
    return None


def simulate_choice_prompt(prompt: Any, keys: Sequence[str]) -> Any:
    """Run a choice-based prompt (select / checkbox / search) with simulated keys.

    *keys* is a sequence of symbolic key names such as ``["down", "down", "enter"]``.

    Returns the prompt result (the value passed to ``event.app.exit(result=...)``).
    """
    captured_kb: list[Any] = [None]

    class FakeApplication:
        """Drop-in replacement for prompt_toolkit.Application."""

        def __init__(
            self,
            *,
            layout: Any = None,
            key_bindings: Any = None,
            full_screen: bool = False,
            erase_when_done: bool = False,
            **kwargs: Any,
        ) -> None:
            captured_kb[0] = key_bindings

        def run(self) -> Any:
            kb = captured_kb[0]
            if kb is None:
                raise RuntimeError("No key_bindings captured from Application")
            app = _FakeApp()
            for key_name in keys:
                key_tuple = _resolve_key(key_name)
                handler = _find_handler(kb.bindings, key_tuple)
                if handler is None:
                    raise ValueError(
                        f"No handler found for key {key_name!r} (resolved to {key_tuple}). "
                        f"Available: {[b.keys for b in kb.bindings]}"
                    )
                # Build the data string (used by e.g. digit-jump handlers)
                data = key_name if len(key_name) == 1 else ""
                event = _FakeEvent(app, data=data)
                try:
                    handler(event)
                except _ExitSentinel as ex:
                    return ex.result
            # If we exhaust the key sequence without an exit, something is wrong
            raise RuntimeError(
                "Key sequence exhausted without an app.exit() call. "
                "Make sure the sequence ends with 'enter' or another exit key."
            )

    with (
        patch("inquirer_ai.prompts.choice_base.Application", FakeApplication),
        patch("inquirer_ai.prompts.search.Application", FakeApplication),
    ):
        return prompt.execute()


# ---------------------------------------------------------------------------
# Core: simulate_input  (simple prompts using pt_prompt)
# ---------------------------------------------------------------------------


def simulate_input(prompt: Any, inputs: Sequence[str]) -> Any:
    """Run a simple prompt (text / confirm / number / password) with mocked input.

    *inputs* is a sequence of strings that ``prompt_toolkit.prompt`` will
    return on successive calls.  For a prompt that only asks once, pass a
    single-element list.

    Returns the prompt result.
    """
    call_iter = iter(inputs)

    def fake_pt_prompt(*args: Any, **kwargs: Any) -> str:
        try:
            return next(call_iter)
        except StopIteration:
            raise EOFError("No more simulated inputs") from None

    # Each prompt module imports pt_prompt differently; patch all known locations
    patches = [
        patch("inquirer_ai.prompts.text.pt_prompt", fake_pt_prompt),
        patch("inquirer_ai.prompts.confirm.pt_prompt", fake_pt_prompt),
        patch("inquirer_ai.prompts.number.pt_prompt", fake_pt_prompt),
    ]
    # Password prompt also uses pt_prompt (if it exists)
    with contextlib.suppress(AttributeError):
        patches.append(patch("inquirer_ai.prompts.password.pt_prompt", fake_pt_prompt))

    for p in patches:
        p.start()
    try:
        return prompt.execute()
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# High-level convenience
# ---------------------------------------------------------------------------


def simulate_keys(prompt: Any, keys: Sequence[str]) -> Any:
    """Unified entry point: detects prompt type and delegates.

    For simple prompts, *keys* should be plain string values (what the user
    would type, without the trailing newline -- that is implicit).

    For choice-based prompts, *keys* should be symbolic key names like
    ``["down", "enter"]``.
    """
    from inquirer_ai.prompts.choice_base import ChoiceBasePrompt
    from inquirer_ai.prompts.search import SearchPrompt

    if isinstance(prompt, (ChoiceBasePrompt, SearchPrompt)):
        return simulate_choice_prompt(prompt, keys)
    return simulate_input(prompt, keys)
