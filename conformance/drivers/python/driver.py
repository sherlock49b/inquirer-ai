#!/usr/bin/env python3
"""Conformance driver for inquirer-ai (Python) — STDIO agent transport.

Runs the 11-prompt conformance scenario via the REAL inquirer-ai library in
agent mode over stdio. Protocol JSONL is emitted by the library on stdout;
the agent's answers are read by the library from stdin. This driver collects
each prompt's RETURN VALUE and writes them as a single JSON array to the file
path given in argv[1] (the "results file").

IMPORTANT: the library uses sys.stdout for the protocol stream, so this driver
must NOT write anything to stdout itself. Diagnostics go to stderr; the result
array goes to the results file.
"""

from __future__ import annotations

import json
import os
import sys

# Force STDIO agent transport regardless of how the process was launched. The
# scenario explicitly requires INQUIRER_AI_MODE=agent and
# INQUIRER_AI_TRANSPORT=stdio (NO socket). Setting these before importing the
# library guarantees the stdio agent path is taken.
os.environ["INQUIRER_AI_MODE"] = "agent"
os.environ["INQUIRER_AI_TRANSPORT"] = "stdio"
os.environ.pop("INQUIRER_AI_SOCKET", None)

import inquirer_ai  # noqa: E402


def _pkg_source(_term: str):
    """Search source for P7.

    The library's `search` prompt takes a `source` callable (term -> choices)
    rather than a static `choices` list. Advertised choices come from calling
    source(""); the answer "requests" matches a choice by NAME and resolves to
    its value "req".
    """
    return [
        {"name": "requests", "value": "req"},
        {"name": "httpx", "value": "hx"},
    ]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: driver.py <results_file>", file=sys.stderr)
        return 2
    results_path = sys.argv[1]

    results: list = []

    # P1 — text/input, default "anon"
    results.append(inquirer_ai.text("Name", default="anon"))

    # P2 — confirm, default True
    results.append(inquirer_ai.confirm("Proceed?", default=True))

    # P3 — number, default 10, min 1, max 1000, integers only
    results.append(
        inquirer_ai.number("Count", default=10, min=1, max=1000, float_allowed=False)
    )

    # P4 — select with a separator and a disabled choice
    results.append(
        inquirer_ai.select(
            "Lang",
            choices=[
                {"name": "Python", "value": "py"},
                {"name": "Go", "value": "go"},
                {"type": "separator", "text": "--"},
                {"name": "Rust", "value": "rs", "disabled": "soon"},
            ],
        )
    )

    # P5 — checkbox, default ["a"]
    results.append(
        inquirer_ai.checkbox(
            "Feat",
            default=["a"],
            choices=[
                {"name": "A", "value": "a"},
                {"name": "B", "value": "b"},
                {"name": "C", "value": "c"},
            ],
        )
    )

    # P6 — rawlist with separator + disabled choice (1-based index over
    # SELECTABLE items only)
    results.append(
        inquirer_ai.rawlist(
            "Ver",
            choices=[
                {"name": "3.13", "value": "313"},
                {"type": "separator", "text": "-"},
                {"name": "3.12", "value": "312", "disabled": True},
                {"name": "3.11", "value": "311"},
            ],
        )
    )

    # P7 — search (source callable advertising two choices)
    results.append(inquirer_ai.search("Pkg", source=_pkg_source))

    # P8 — password, default "def".
    # NOTE: the inquirer_ai.password() convenience function does not expose a
    # `default` parameter, but PasswordPrompt itself accepts `default` (via
    # BasePrompt) and returns it when the agent answers null. Construct the
    # prompt class directly to honor the scenario's default="def".
    results.append(inquirer_ai.PasswordPrompt("Token", default="def").execute())

    # P9 — expand; key "Y" is uppercase ON PURPOSE (library lowercases to "y")
    results.append(
        inquirer_ai.expand(
            "Conflict",
            choices=[
                {"key": "Y", "name": "Yes", "value": "yes"},
                {"key": "n", "name": "No", "value": "no"},
            ],
        )
    )

    # P10 — autocomplete (unconstrained free text)
    results.append(inquirer_ai.autocomplete("Free", choices=["Python", "Go"]))

    # P11 — path, default "." (no ~ expansion on the returned value)
    results.append(inquirer_ai.path("Dir", default="."))

    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh)
        fh.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
