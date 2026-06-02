#!/usr/bin/env python3
"""Cross-language conformance runner for inquirer-ai (stdlib only).

Runs the SAME 11-prompt scenario (see scenario.md) through the Python, Rust, Go,
and TypeScript drivers, each driving the REAL library in STDIO AGENT MODE
(INQUIRER_AI_MODE=agent, INQUIRER_AI_TRANSPORT=stdio). For every language it:

  * pipes conformance/fixture.jsonl to the driver's stdin,
  * passes a temp results-file path as argv[1],
  * captures the driver's stdout (the protocol JSONL stream),
  * reads back the results array the driver wrote to the results file.

It then NORMALIZES and cross-compares all four languages:

  * handshake (ignoring the `socket` and `total` fields; `version` recorded
    separately and asserted equal across all four),
  * the SEQUENCE and COUNT of protocol messages (prompts / validation_errors
    must line up position-for-position),
  * each prompt payload object (deep structural compare by value, key order
    ignored, 100 == 100.0),
  * each validation_error message (compared by value; a known language-specific
    transport wrapper prefix is stripped first),
  * the final results array (numeric-normalized).

Python is treated as the REFERENCE, but ALL pairwise divergences are reported.
Exits non-zero if ANY divergence is found.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixture.jsonl")
DRIVERS = os.path.join(HERE, "drivers")

LANGS = ["python", "rust", "go", "typescript"]

# Languages compared against the Python reference for pairwise reporting.
REFERENCE = "python"

# Handshake fields ignored entirely during comparison (transport-specific).
HANDSHAKE_IGNORE = {"socket", "total"}

# Validation-error messages are compared verbatim across languages: the protocol
# message MUST be byte-identical, with no transport wrapper prefixes. (Earlier a
# Go-specific "prompt error: validation failed: " prefix was tolerated here; that
# divergence has been fixed at the source, so the runner now compares raw messages
# and would flag any reintroduced wrapper as a divergence.)
VALIDATION_WRAPPER_PREFIXES: list[str] = []


# --------------------------------------------------------------------------- #
# Driver invocation
# --------------------------------------------------------------------------- #

def driver_command(lang: str, results_file: str) -> list[str]:
    """Return the argv to run a language's driver (exact commands per reports)."""
    if lang == "python":
        return [
            "uv", "run", "--directory", os.path.join(REPO, "python"),
            "python", os.path.join(DRIVERS, "python", "driver.py"),
            results_file,
        ]
    if lang == "rust":
        return [
            "cargo", "run", "--quiet",
            "--manifest-path", os.path.join(DRIVERS, "rust", "Cargo.toml"),
            "--", results_file,
        ]
    if lang == "go":
        return [
            "go", "-C", os.path.join(DRIVERS, "go"), "run", ".",
            results_file,
        ]
    if lang == "typescript":
        return [
            "node", os.path.join(DRIVERS, "typescript", "driver.mjs"),
            results_file,
        ]
    raise ValueError(f"unknown language: {lang}")


class RunResult:
    def __init__(self, lang: str):
        self.lang = lang
        self.handshake: dict | None = None
        self.version: Any = None
        self.messages: list[dict] = []   # all non-handshake protocol messages, in order
        self.results: list | None = None
        self.stderr: str = ""
        self.returncode: int = 0
        self.error: str | None = None     # harness-level failure (couldn't run/parse)


def run_driver(lang: str) -> RunResult:
    rr = RunResult(lang)
    with open(FIXTURE, "rb") as fh:
        fixture_bytes = fh.read()

    env = dict(os.environ)
    env["INQUIRER_AI_MODE"] = "agent"
    env["INQUIRER_AI_TRANSPORT"] = "stdio"
    env.pop("INQUIRER_AI_SOCKET", None)

    with tempfile.NamedTemporaryFile(
        prefix=f"conformance_{lang}_", suffix=".json", delete=False
    ) as tf:
        results_file = tf.name

    try:
        proc = subprocess.run(
            driver_command(lang, results_file),
            input=fixture_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=REPO,
            timeout=600,
        )
        rr.returncode = proc.returncode
        rr.stderr = proc.stderr.decode("utf-8", "replace")

        if proc.returncode != 0:
            rr.error = f"driver exited {proc.returncode}"
            return rr

        # Parse stdout into protocol messages.
        for i, line in enumerate(proc.stdout.decode("utf-8", "replace").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                rr.error = f"stdout line {i} is not JSON: {e}: {line!r}"
                return rr
            if obj.get("kind") == "handshake":
                rr.version = obj.get("version")
                rr.handshake = obj
            else:
                rr.messages.append(obj)

        if rr.handshake is None:
            rr.error = "no handshake emitted on stdout"
            return rr

        # Read the results array.
        try:
            with open(results_file, "r", encoding="utf-8") as fh:
                rr.results = json.loads(fh.read())
        except (OSError, json.JSONDecodeError) as e:
            rr.error = f"could not read results file: {e}"
            return rr

    except FileNotFoundError as e:
        rr.error = f"toolchain missing: {e}"
    except subprocess.TimeoutExpired:
        rr.error = "driver timed out (600s)"
    finally:
        try:
            os.unlink(results_file)
        except OSError:
            pass
    return rr


# --------------------------------------------------------------------------- #
# Normalization + comparison
# --------------------------------------------------------------------------- #

def normalize(value: Any) -> Any:
    """Recursively normalize a parsed-JSON value for structural comparison.

    * numbers: integral floats collapse to int (100.0 -> 100) so 100 == 100.0.
    * dicts: keys preserved but values normalized (dict equality ignores order).
    * lists: elementwise normalized (order is significant).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    return value


def strip_validation_wrapper(msg: Any) -> Any:
    if not isinstance(msg, str):
        return msg
    out = msg
    changed = True
    while changed:
        changed = False
        for pref in VALIDATION_WRAPPER_PREFIXES:
            if out.startswith(pref):
                out = out[len(pref):]
                changed = True
    return out


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Divergence:
    def __init__(self, category: str, locus: str, field: str,
                 values: dict[str, Any]):
        self.category = category   # e.g. "handshake", "prompt", "validation_error", "results", "sequence", "version"
        self.locus = locus         # e.g. "step 4 (select 'Lang')"
        self.field = field
        self.values = values       # lang -> value

    def render(self) -> str:
        head = f"[{self.category}] {self.locus} — field `{self.field}`"
        lines = [head]
        for lang in LANGS:
            if lang in self.values:
                lines.append(f"    {lang:<11}: {jdump(self.values[lang])}")
        return "\n".join(lines)


def classify_messages(rr: RunResult) -> tuple[list[dict], list[dict]]:
    prompts = [m for m in rr.messages if m.get("kind") == "prompt"]
    verrors = [m for m in rr.messages if m.get("kind") == "validation_error"]
    return prompts, verrors


def message_kind_sequence(rr: RunResult) -> list[str]:
    return [m.get("kind", "?") for m in rr.messages]


def prompt_label(payload: dict, idx: int) -> str:
    t = payload.get("type", "?")
    m = payload.get("message", "?")
    return f"prompt #{idx + 1} ({t} {m!r})"


# --------------------------------------------------------------------------- #
# Main comparison driver
# --------------------------------------------------------------------------- #

def main() -> int:
    print("=" * 78)
    print("inquirer-ai cross-language conformance runner")
    print("fixture:", FIXTURE)
    print("languages:", ", ".join(LANGS))
    print("=" * 78)

    runs: dict[str, RunResult] = {}
    fatal = False
    for lang in LANGS:
        print(f"\n>>> running {lang} driver ...", flush=True)
        rr = run_driver(lang)
        runs[lang] = rr
        if rr.error:
            print(f"    FATAL: {rr.error}")
            if rr.stderr.strip():
                print("    stderr:")
                for ln in rr.stderr.strip().splitlines():
                    print(f"        {ln}")
            fatal = True
            continue
        p, v = classify_messages(rr)
        print(f"    ok: handshake v{rr.version}, "
              f"{len(rr.messages)} protocol messages "
              f"({len(p)} prompt, {len(v)} validation_error), "
              f"{len(rr.results) if rr.results is not None else '?'} results")

    if fatal:
        print("\n" + "=" * 78)
        print("RESULT: FAIL — one or more drivers could not run (see FATAL above)")
        print("=" * 78)
        return 2

    divergences: list[Divergence] = []
    ref = runs[REFERENCE]

    # ---- 1. version (all four must be equal) ----
    versions = {lang: runs[lang].version for lang in LANGS}
    if len(set(jdump(v) for v in versions.values())) != 1:
        divergences.append(Divergence(
            "version", "handshake", "version", versions))

    # ---- 2. handshake (minus ignored fields) ----
    def hs_norm(hs: dict) -> dict:
        return normalize({k: val for k, val in hs.items()
                          if k not in HANDSHAKE_IGNORE})
    ref_hs = hs_norm(ref.handshake)
    for lang in LANGS:
        if lang == REFERENCE:
            continue
        other = hs_norm(runs[lang].handshake)
        if other != ref_hs:
            keys = set(ref_hs) | set(other)
            for k in sorted(keys):
                if ref_hs.get(k) != other.get(k):
                    divergences.append(Divergence(
                        "handshake", "handshake", k,
                        {REFERENCE: ref_hs.get(k), lang: other.get(k)}))

    # ---- 3. message sequence (kind-by-kind, count + positions) ----
    ref_seq = message_kind_sequence(ref)
    seq_mismatch = False
    for lang in LANGS:
        if lang == REFERENCE:
            continue
        other_seq = message_kind_sequence(runs[lang])
        if other_seq != ref_seq:
            seq_mismatch = True
            divergences.append(Divergence(
                "sequence", "protocol stream", "message-kind sequence",
                {REFERENCE: ref_seq, lang: other_seq}))

    # ---- 4. per-message structural comparison ----
    # Compare position-by-position over the shortest common length. If the
    # sequence already diverged we still compare the overlap to surface the
    # field-level differences.
    n = min(len(runs[lang].messages) for lang in LANGS)
    prompt_idx = 0
    verr_idx = 0
    for i in range(n):
        kinds = {lang: runs[lang].messages[i].get("kind") for lang in LANGS}
        ref_kind = kinds[REFERENCE]

        if len(set(kinds.values())) != 1:
            # Different kinds at the same position -> already covered by the
            # sequence divergence; skip field compare for this slot.
            if ref_kind == "prompt":
                prompt_idx += 1
            elif ref_kind == "validation_error":
                verr_idx += 1
            continue

        if ref_kind == "prompt":
            locus = prompt_label(runs[REFERENCE].messages[i], prompt_idx)
            ref_payload = normalize(runs[REFERENCE].messages[i])
            for lang in LANGS:
                if lang == REFERENCE:
                    continue
                other_payload = normalize(runs[lang].messages[i])
                if other_payload != ref_payload:
                    keys = set(ref_payload) | set(other_payload)
                    for k in sorted(keys):
                        if ref_payload.get(k) != other_payload.get(k):
                            divergences.append(Divergence(
                                "prompt", locus, k,
                                {REFERENCE: ref_payload.get(k),
                                 lang: other_payload.get(k)}))
            prompt_idx += 1

        elif ref_kind == "validation_error":
            locus = f"validation_error #{verr_idx + 1}"
            ref_msg_raw = runs[REFERENCE].messages[i].get("message")
            ref_msg = strip_validation_wrapper(ref_msg_raw)
            for lang in LANGS:
                if lang == REFERENCE:
                    continue
                other_raw = runs[lang].messages[i].get("message")
                other_msg = strip_validation_wrapper(other_raw)
                if other_msg != ref_msg:
                    divergences.append(Divergence(
                        "validation_error", locus, "message",
                        {REFERENCE: ref_msg, lang: other_msg}))
            verr_idx += 1

    # ---- 5. final results array ----
    ref_results = normalize(ref.results)
    for lang in LANGS:
        if lang == REFERENCE:
            continue
        other_results = normalize(runs[lang].results)
        if other_results != ref_results:
            # Report element-by-element where possible.
            if (isinstance(other_results, list)
                    and isinstance(ref_results, list)
                    and len(other_results) == len(ref_results)):
                for idx in range(len(ref_results)):
                    if ref_results[idx] != other_results[idx]:
                        divergences.append(Divergence(
                            "results", f"results[{idx}]", f"element {idx}",
                            {REFERENCE: ref_results[idx],
                             lang: other_results[idx]}))
            else:
                divergences.append(Divergence(
                    "results", "results array", "whole array",
                    {REFERENCE: ref_results, lang: other_results}))

    # ---- report ----
    print("\n" + "=" * 78)
    print("CROSS-LANGUAGE COMPARISON (reference: %s)" % REFERENCE)
    print("=" * 78)

    # Quick parity matrix for the results array.
    print("\nfinal results arrays (normalized):")
    for lang in LANGS:
        print(f"  {lang:<11}: {jdump(normalize(runs[lang].results))}")

    print("\nprotocol message counts:")
    for lang in LANGS:
        p, v = classify_messages(runs[lang])
        print(f"  {lang:<11}: {len(runs[lang].messages)} total "
              f"({len(p)} prompt, {len(v)} validation_error)")

    if not divergences:
        print("\n" + "=" * 78)
        print("RESULT: PASS — FULL PARITY — 0 divergences across all 4 languages")
        print("=" * 78)
        return 0

    # Group divergences by category for a readable report.
    print(f"\n!!! {len(divergences)} DIVERGENCE(S) FOUND !!!\n")
    by_cat: dict[str, list[Divergence]] = {}
    for d in divergences:
        by_cat.setdefault(d.category, []).append(d)
    for cat in ["version", "handshake", "sequence", "prompt",
                "validation_error", "results"]:
        if cat not in by_cat:
            continue
        print("-" * 78)
        print(f"## {cat.upper()} divergences ({len(by_cat[cat])})")
        print("-" * 78)
        for d in by_cat[cat]:
            print(d.render())
            print()

    print("=" * 78)
    print(f"RESULT: FAIL — {len(divergences)} divergence(s); "
          f"see field/step/per-language values above")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main())
