# Cross-language conformance scenario

This directory holds the cross-language **conformance harness** for inquirer-ai.
Its purpose is to prove that the Python, Rust, Go, and TypeScript implementations
of the library emit a **byte-for-byte identical** agent protocol (handshake +
prompt payloads + validation errors) and return identical answers for one fixed,
carefully chosen scenario.

All four drivers exercise the **REAL** library in **STDIO AGENT MODE**:

```
INQUIRER_AI_MODE=agent
INQUIRER_AI_TRANSPORT=stdio      # NO socket
```

In this mode the library reads the agent's answers from **stdin** (one JSON
object per line) and writes the protocol JSONL stream to **stdout** (a handshake
line, one `prompt` line per library read, and a `validation_error` line whenever
an answer fails validation). Each driver collects every prompt's **return value**
and writes them as a single JSON array to the **results file** path given in
`argv[1]`. Protocol stays on stdout; results go to the file; stderr stays empty.

## The 11 prompts (exact order, exact wording)

The wording, choices, and options below are **load-bearing** — the runner
compares the emitted payloads byte-for-byte after JSON parse.

| # | type | message | options |
|---|------|---------|---------|
| P1 | text/input | `Name` | `default="anon"` |
| P2 | confirm | `Proceed?` | `default=true` |
| P3 | number | `Count` | `default=10`, `min=1`, `max=1000`, `float_allowed=false` |
| P4 | select | `Lang` | choices: `{Python:py}`, `{Go:go}`, separator `--`, `{Rust:rs, disabled:"soon"}` |
| P5 | checkbox | `Feat` | `default=["a"]`, choices: `{A:a}`, `{B:b}`, `{C:c}` |
| P6 | rawlist | `Ver` | choices: `{3.13:313}`, separator `-`, `{3.12:312, disabled:true}`, `{3.11:311}` |
| P7 | search | `Pkg` | choices: `{requests:req}`, `{httpx:hx}` (supplied via a `source` callable) |
| P8 | password | `Token` | `default="def"` |
| P9 | expand | `Conflict` | choices: `{key:"Y", Yes:yes}`, `{key:"n", No:no}` — key `Y` is uppercase **on purpose** and must be lowercased to `y` |
| P10 | autocomplete | `Free` | choices: `["Python","Go"]` (unconstrained free text) |
| P11 | path | `Dir` | `default="."` (no `~` expansion of the returned value) |

### Notes on library API shape (per-driver, not divergences)

- `search` (P7) takes a **`source` callable** (`term -> choices`) in every
  language rather than a static `choices` list. Each driver wraps the two
  scenario choices in a source that returns them; the library advertises the
  resolved choices in the agent payload (`searchable:true`).
- Python's `password()` convenience helper does not expose `default`, so the
  Python driver constructs `PasswordPrompt("Token", default="def")` directly.

## The fixture (`fixture.jsonl`)

One JSON object per **library read**, in order. This includes the three
validation **retries** (P3, P4, P6). There are **14** answer lines for the 11
logical prompts.

```jsonl
{"answer":""}            # P1 -> ""   (verbatim, NOT the default)
{"answer":null}          # P2 -> true (the default)
{"answer":"3.5"}         # P3 -> validation_error "Decimal numbers are not allowed"; prompt re-sent
{"answer":"1e2"}         # P3 retry -> 100
{"answer":"rs"}          # P4 -> validation_error (rs is disabled); prompt re-sent
{"answer":"go"}          # P4 retry -> "go"
{"answer":["b","C"]}     # P5 -> ["b","c"]  (b by value, C by name)
{"answer":1.5}           # P6 -> validation_error (non-integer index); prompt re-sent
{"answer":2}             # P6 retry -> "311" (2nd SELECTABLE: separator + disabled 312 excluded)
{"answer":"requests"}    # P7 -> "req" (name resolved to value)
{"answer":null}          # P8 -> "def" (the default)
{"answer":"y"}           # P9 -> "yes" (key Y lowercased)
{"answer":"whatever"}    # P10 -> "whatever" (verbatim, unconstrained)
{"answer":"~/proj"}      # P11 -> "~/proj" (verbatim, no ~ expansion)
```

## Expected protocol stream (per language)

Every language must emit the **same number of stdout lines in the same order**:

- **1** handshake (`{"kind":"handshake","protocol":"inquirer-ai","version":"0.3.1",...}`)
- **14** `prompt` lines = 11 distinct prompts + 3 re-sends (the library re-emits
  the full prompt payload on each validation retry: P3, P4, P6).
- **3** `validation_error` lines, at the positions following P3, P4, P6:
  - P3: `Decimal numbers are not allowed`
  - P4: invalid choice (`rs` is disabled)
  - P6: invalid choice (non-integer index `1.5`)

> Total = **18** stdout lines.
>
> (The original task brief's summary line said "11 prompts + 2 validation_errors";
> that undercounts. The fixture/scenario unambiguously prescribes **3** validation
> retries, and all four libraries correctly emit 3 validation_errors + 3 re-sends.
> This is a documentation typo in the brief, not a library divergence.)

## Expected final results array

The single JSON array each driver writes to its results file:

```json
["", true, 100, "go", ["b","c"], "311", "req", "def", "yes", "whatever", "~/proj"]
```

Numerics are normalized by the runner: `100` and `100.0` compare equal (Rust
serializes the P3 number as `100.0`).

## What the runner checks

`run.py` runs each driver with `fixture.jsonl` on stdin and cross-compares all
four languages (Python is the reference, but all pairwise diffs are reported):

1. **Handshake** — equal after ignoring `socket` and `total`; `version` is
   recorded separately and all four must match.
2. **Message sequence** — identical count and ordering of `prompt` /
   `validation_error` messages (validation_errors at the same positions).
3. **Each prompt payload** — deep structural compare by value (key order
   ignored, `100`==`100.0`): `type`, `message`, `default`, `choices`, `min`,
   `max`, `step`, `mask`, etc.
4. **Each validation_error message** — compared by value. (Some libraries wrap
   the contract message with a language-specific prefix, e.g. Go prepends
   `prompt error: validation failed: `; the runner strips such known wrapper
   prefixes before comparing the message text.)
5. **Final results array** — byte-exact after numeric normalization.

Any divergence prints the field, the prompt step, and the differing value per
language, and the runner exits non-zero.
