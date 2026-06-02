# inquirer-ai Agent Protocol Specification v2.1

## Overview

The inquirer-ai agent protocol enables AI agents to drive interactive CLI tools programmatically via a JSON Lines (JSONL) protocol. Programs built with inquirer-ai automatically support two modes:

- **Terminal mode**: Interactive UI with cursor navigation, key bindings, and styled output (default when stdin is a TTY)
- **Agent mode**: JSON line protocol for structured communication (default when stdin is not a TTY, or `INQUIRER_AI_MODE=agent`)

## Mode Detection

Mode and transport are resolved with the following precise rules (all values
of `INQUIRER_AI_MODE` are matched case-insensitively):

1. **is_human** = `INQUIRER_AI_MODE == "human"`. Terminal mode is forced.
2. **socket_requested** = `INQUIRER_AI_SOCKET` is set and non-empty, **OR**
   `INQUIRER_AI_MODE == "agent"`.
3. **is_agent** = (NOT is_human) AND (socket_requested OR stdin is not a TTY).
4. Otherwise → terminal mode.

This means:

- A plain piped, non-TTY invocation with no `INQUIRER_AI_MODE`/`INQUIRER_AI_SOCKET`
  stays in **stdio** agent transport (backwards compatible).
- Setting `INQUIRER_AI_SOCKET` (even on a TTY) activates the **socket** transport.
- `INQUIRER_AI_MODE=human` always forces terminal mode regardless of TTY or
  socket settings.

### Transport selection (when is_agent)

Use the **socket** transport if and only if:

- socket_requested is true, AND
- `INQUIRER_AI_TRANSPORT` is **not** `"stdio"`, AND
- Unix domain sockets are available on the platform.

The socket path is `INQUIRER_AI_SOCKET` if set, otherwise `/tmp/inquirer-ai-{pid}.sock`.

Otherwise, use the **stdio** agent transport (honoring `INQUIRER_AI_FD` /
`INQUIRER_AI_FD_OUT` / `INQUIRER_AI_FD_IN`).

## Transport

### Socket transport (default in agent mode)

In agent mode, the tool creates a Unix domain socket and advertises its path in the handshake. Each prompt is served on a separate socket connection, allowing agents to interact with independent one-shot commands (`nc -U` or `socat`).

```bash
# Agent starts the CLI, reads handshake from stdout
INQUIRER_AI_MODE=agent my-cli > /tmp/handshake.txt &
SOCK=$(jq -r .socket /tmp/handshake.txt)

# Each prompt is a separate connection
echo '{"answer":"feat"}' | nc -U -q1 $SOCK
echo '{"answer":"add login"}' | nc -U -q1 $SOCK
```

See [`socket-transport.md`](socket-transport.md) for the full specification.

### Stdio transport (legacy)

When `INQUIRER_AI_TRANSPORT=stdio` is set, or on platforms without Unix sockets, protocol messages use stdout (tool → agent) and stdin (agent → tool). Programs MUST NOT write non-protocol output to stdout in agent mode — use stderr for logs, progress, and user-facing text.

### Optional: fd-based communication (stdio transport only)

When `INQUIRER_AI_FD` is set, the tool uses dedicated file descriptors instead of stdin/stdout:

| Variable | Default | Description |
|----------|---------|-------------|
| `INQUIRER_AI_FD_OUT` | `1` (stdout) | fd the tool writes prompts to |
| `INQUIRER_AI_FD_IN` | `0` (stdin) | fd the tool reads answers from |

Example: `INQUIRER_AI_FD_OUT=3 INQUIRER_AI_FD_IN=4 ./my-cli` frees stdout/stdin for normal program I/O.

## Message Types

Every protocol message is a JSON object with a `kind` field:

| kind | Direction | Description |
|------|-----------|-------------|
| `handshake` | tool → agent | Protocol metadata (first line) |
| `handshake_ack` | agent → tool | Agent capabilities (optional) |
| `prompt` | tool → agent | A question for the agent |
| `validation_error` | tool → agent | Previous answer was invalid, prompt will be re-sent |
| `error` | tool → agent | Fatal error, program will exit |

## Protocol Flow

```
Program                                 Agent
  │                                       │
  ├── {"kind":"handshake",...} ──────────►│
  │◄── {"kind":"handshake_ack",...} ──────┤  (optional)
  │                                       │
  ├── {"kind":"prompt", step:1,...} ─────►│
  │◄── {"answer": ...} ──────────────────┤
  │                                       │
  ├── {"kind":"prompt", step:2,...} ─────►│
  │◄── {"answer": "invalid!"} ───────────┤
  ├── {"kind":"validation_error",...} ───►│
  ├── {"kind":"prompt", step:2,...} ─────►│  (re-sent)
  │◄── {"answer": "valid"} ──────────────┤
  │                                       │
  ├── {"kind":"prompt", step:3,...} ─────►│
  │◄── {"answer": ...} ──────────────────┤
  │                                       │
```

## Handshake

The first line emitted by the program is a handshake. It is sent exactly once, before the first prompt.

```json
{
  "kind": "handshake",
  "protocol": "inquirer-ai",
  "version": "0.3.2",
  "format": "jsonl",
  "socket": "/tmp/inquirer-ai-29481.sock",
  "interaction": "sequential",
  "total": 5,
  "description": "Interactive prompt protocol over Unix socket. Connect to read a prompt, send a JSON answer, receive status. One connection per prompt.",
  "example_response": {"answer": "<value>"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | Always `"handshake"` |
| `protocol` | string | yes | Always `"inquirer-ai"` |
| `version` | string | yes | Semantic version of the library |
| `format` | string | yes | Always `"jsonl"` |
| `socket` | string | no | Unix socket path for agent interaction. Present when socket transport is active. |
| `interaction` | string | yes | Always `"sequential"` |
| `total` | number \| null | no | Total number of prompts, `null` if unknown |
| `description` | string | yes | Human-readable protocol description |
| `example_response` | object | yes | Example response format |

### Handshake Acknowledgment (optional)

The agent MAY reply with a `handshake_ack` before its first answer. If the tool receives an `answer` instead, it assumes a basic agent with no special capabilities.

```json
{
  "kind": "handshake_ack",
  "agent": "claude",
  "capabilities": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | Always `"handshake_ack"` |
| `agent` | string | no | Agent identifier |
| `capabilities` | string[] | no | Reserved for future capability negotiation |

## Prompt Objects

```json
{
  "kind": "prompt",
  "type": "input",
  "message": "What is your name?",
  "default": null,
  "step": 1,
  "total": 5
}
```

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | Always `"prompt"` |
| `type` | string | yes | Prompt type identifier |
| `message` | string | yes | The question to display |
| `default` | any | no | Default value if answer is null |
| `step` | number | yes | 1-based step number |
| `total` | number \| null | no | Total prompts, `null` if unknown (dynamic flows) |

## Response Format

Every response MUST be a JSON object with an `answer` key:

```json
{"answer": <value>}
```

The value type depends on the prompt type. Sending `null` as the answer uses the prompt's default value.

## Validation Error and Retry

There is a single **unified budget of exactly 3 answer attempts per prompt**, on
both the stdio and socket transports. This budget is shared between type/coercion
validation and any user-supplied `validate()` callback — there is **one** counter,
not two independent ones.

- Attempt 1 invalid → send `{"kind":"validation_error","message":...}` and re-send the prompt.
- Attempt 2 invalid → send `{"kind":"validation_error","message":...}` and re-send the prompt.
- Attempt 3 invalid → send `{"kind":"error","message":...}` and exit with a non-zero status.

So a prompt emits **at most 2 `validation_error` messages, then 1 fatal `error`**.

```json
{"kind": "validation_error", "message": "Invalid choice: \"java\". Valid: [\"python\", \"go\"]"}
```

An empty line, EOF, or closed stdin is **not** a retry — it is an immediate fatal
abort (see Fatal Error below).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | Always `"validation_error"` |
| `message` | string | yes | Human-readable error description |

### Canonical error message strings

These messages MUST be used verbatim across all implementations:

| Condition | Message |
|-----------|---------|
| `checkbox` with no selection but required | `At least one choice is required` |
| Answer line is not parseable as JSON | `Invalid JSON response: <detail>` |
| Answer parsed but not an object, or missing the `"answer"` key | `Answer must be a JSON object with an "answer" field` |

## Fatal Error

For unrecoverable errors (empty line / EOF / closed stdin, or the 3rd failed
attempt):

```json
{"kind": "error", "message": "stdin closed unexpectedly"}
```

The program exits with a non-zero status after emitting this message. A
non-`ValidationError` raised by a user `validate()` callback is caught and
reported as `{"kind":"error",...}` before exit.

## Prompt Types

### `input` — Text Input

```json
{"kind": "prompt", "type": "input", "message": "What is your name?", "default": null, "step": 1, "total": 3}
```

**Response**: `{"answer": "Alice"}` → returns `"Alice"`
**Response**: `{"answer": null}` → returns the `default` (or `""` if unset)
**Response**: `{"answer": ""}` → returns `""` verbatim (the default is applied **only** when the raw answer is `null`, never for an explicit empty string)

---

### `confirm` — Yes/No

```json
{"kind": "prompt", "type": "confirm", "message": "Continue?", "default": false, "step": 2, "total": 3}
```

**Response**: `{"answer": true}` or `{"answer": false}`
**Response**: `{"answer": "yes"}` → coerced to `true`
**Response**: `{"answer": null}` → returns the prompt's `default` (a bool; the default itself defaults to `false`)

Accepted truthy strings (case-insensitive): `y`, `yes`, `true`, `1`
Accepted falsy strings (case-insensitive): `n`, `no`, `false`, `0`
Booleans are accepted as-is.

---

### `select` — Single Choice

```json
{
  "kind": "prompt",
  "type": "select",
  "message": "Pick a language",
  "default": null,
  "step": 1,
  "total": null,
  "choices": [
    {"name": "Python", "value": "python"},
    {"name": "Go", "value": "go", "description": "Systems language"},
    {"name": "Rust", "value": "rust", "disabled": "coming soon"},
    {"type": "separator", "text": "────────"}
  ]
}
```

**Response**: `{"answer": "python"}` — by value or by name

Matching is **type-aware** (see [Value Matching](#value-matching)): the answer
matches a choice's `value` only if it has the same JSON type and value, or it is a
string exactly equal to the choice's `name`. Disabled choices are **rejected**
(skipped from matching). Separators are non-selectable display elements (never
matchable) and appear in the `choices` payload as separator objects.

---

### `checkbox` — Multiple Choice

```json
{
  "kind": "prompt",
  "type": "checkbox",
  "message": "Select features",
  "default": ["docker"],
  "step": 3,
  "total": 5,
  "choices": [
    {"name": "Docker", "value": "docker"},
    {"name": "CI/CD", "value": "ci"},
    {"type": "separator", "text": "── Testing ──"},
    {"name": "Unit tests", "value": "tests"},
    {"name": "Load testing", "value": "load", "disabled": "coming soon"}
  ]
}
```

**Response**: `{"answer": ["docker", "tests"]}` — array of values or names (type-aware match per element; disabled choices are rejected; separators are non-selectable and included in the payload). If a selection is required but none is given, the canonical error is `At least one choice is required`.

---

### `password` — Masked Input

```json
{"kind": "prompt", "type": "password", "message": "Enter token", "default": null, "mask": "*", "step": 1, "total": 1}
```

**Response**: `{"answer": "s3cret"}` → returns plain text
**Response**: `{"answer": null}` → returns the prompt's `default` (`""` if unset)

`mask` indicates the terminal display character. `null` means fully hidden. The agent receives and sends plain text regardless.

---

### `number` — Numeric Input

```json
{
  "kind": "prompt",
  "type": "number",
  "message": "Port",
  "default": 8080,
  "min": 1024,
  "max": 65535,
  "float_allowed": false,
  "step": 2,
  "total": 4
}
```

**Response**: `{"answer": 3000}` — integer or float
**Response**: `{"answer": "3000"}` — string is parsed as a number per the grammar below

Coercion and validation proceed in this exact order:

1. `null` and a `default` is present → use the default.
2. JSON number (but **not** a boolean) → use it directly.
3. JSON string → trim leading/trailing ASCII whitespace, then the remainder MUST
   fully match the regex below, else `ValidationError: Not a valid number: <repr>`.
   The validated string is parsed with the native float parser.

   ```
   ^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$
   ```

   (Optional sign; **required** integer part; optional `.fraction`; optional
   exponent.) This **rejects** `"1_000"`, `"3abc"`, `"0x10"`, `".5"`, `"5."`,
   `""`, `"+"`, and **accepts** `"1e3"` → 1000, `"  5  "` → 5, `"3.5"`, `"-2"`,
   `"1E-3"`.
4. Any other JSON type → `Expected a number, got <type>`.
5. Non-finite values (NaN/Inf) are rejected → `Not a valid number`.
6. If `float_allowed` is false: the value must be integral (`n == trunc(n)`),
   else `Decimal numbers are not allowed`; it is then coerced to an integer.
7. Finally, `min`/`max` bounds are enforced.

The returned value may be language-idiomatic (e.g. a Python `int` for an integral
result) as long as the accept/reject decision and the numeric value match across
implementations.

---

### `editor` — External Editor

```json
{"kind": "prompt", "type": "editor", "message": "Enter description", "default": null, "postfix": ".txt", "step": 1, "total": 1}
```

**Response**: `{"answer": "Multi-line\ntext content"}` → returns text string
**Response**: `{"answer": null}` → returns the `default` (an explicit `""` returns `""` verbatim)

In terminal mode, opens `$VISUAL` or `$EDITOR`. The editor command is split with
quote-aware shell-word splitting and exec'd directly (no shell, no injection);
the temp file is created with a randomized name, mode `0600`, `O_EXCL`/`create_new`
(no clobber, no symlink follow), and removed on every exit path. In agent mode,
the agent provides the text directly.

---

### `search` — Searchable Selection

```json
{
  "kind": "prompt",
  "type": "search",
  "message": "Find a package",
  "searchable": true,
  "step": 1,
  "total": 2,
  "choices": [
    {"name": "requests — HTTP client", "value": "requests"},
    {"name": "httpx — Async HTTP", "value": "httpx"}
  ]
}
```

**Response**: `{"answer": "httpx"}` — by value or name

Resolution: if the answer matches an advertised choice (type-aware `value` match
**or** exact `name` match), return that choice's **value**; otherwise return the
answer **verbatim** as a string. This keeps dynamic/async search sources safe —
an answer that does not correspond to any advertised choice is still accepted.

The `choices` array contains the initial (unfiltered) results. For an async/
dynamic source, the socket transport advertises the resolved initial choices
(never an empty array).

---

### `rawlist` — Numbered Selection

```json
{
  "kind": "prompt",
  "type": "rawlist",
  "message": "Pick a version",
  "default": null,
  "step": 1,
  "total": 1,
  "choices": [
    {"name": "3.13", "value": "3.13"},
    {"name": "3.12", "value": "3.12"}
  ]
}
```

**Response**: `{"answer": 1}` — by 1-based **integer** index
**Response**: `{"answer": "3.13"}` — by value or name

The index must be a 1-based **integer**; non-integer indices (e.g. `1.5`) are
rejected (not truncated). The index range and value/name matching are over the
**selectable** list only — that is, `choices` with separators and disabled
choices removed. The `choices` array in the payload is exactly that selectable
list, numbered `1..n` (separators and disabled choices are filtered out of both
the payload and the indexing).

---

### `expand` — Key-based Selection

```json
{
  "kind": "prompt",
  "type": "expand",
  "message": "Conflict resolution",
  "default": null,
  "step": 1,
  "total": 1,
  "choices": [
    {"key": "y", "name": "Overwrite", "value": "overwrite"},
    {"key": "n", "name": "Skip", "value": "skip"},
    {"key": "a", "name": "Abort", "value": "abort"}
  ]
}
```

**Response**: `{"answer": "y"}` — by key, value, or name

Keys are lowercased at construction, in the advertised payload, and when
comparing the answer. A non-string `key` in a choice is an `InvalidChoiceError`.

---

### `path` — File/Directory Path

```json
{"kind": "prompt", "type": "path", "message": "Output directory", "default": null, "only_directories": false, "step": 1, "total": 1}
```

**Response**: `{"answer": "/home/user/project"}` → returns the path string **verbatim**
**Response**: `{"answer": null}` → returns the `default` (an explicit `""` returns `""` verbatim)

The returned value is returned exactly as given: no `~`/`$VAR` expansion, no
`Clean`/normalization. In agent mode the path is **not** required to exist, and
`only_directories` is advisory only.

---

### `autocomplete` — Text with Suggestions

```json
{
  "kind": "prompt",
  "type": "autocomplete",
  "message": "Language",
  "default": null,
  "step": 1,
  "total": 1,
  "choices": ["Python", "Go", "Rust", "TypeScript"]
}
```

**Response**: `{"answer": "Python"}` — any string is accepted and returned **verbatim** (unconstrained by `choices`); `null` returns the `default`

## Choice Object Schema

```json
{
  "name": "Display Name",
  "value": "return_value",
  "disabled": false,
  "short": "DN",
  "description": "Additional context shown when focused"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Display text |
| `value` | any | no | Value returned when selected; **defaults to `name`** if absent |
| `disabled` | bool \| string | no | Disabled iff `true` **or** a non-empty string (see below) |
| `short` | string | no | Abbreviated display after selection |
| `description` | string | no | Context shown when choice is focused |

### Disabled semantics

A choice is **disabled** iff `disabled === true` **OR** `disabled` is a non-empty
string. `false`, an absent field, and the empty string `""` all leave the choice
**enabled**. Disabled choices are never matchable.

### Value Matching

Matching an agent answer against a choice is **type-aware**:

- The answer matches a choice's `value` only if it has the **same JSON type and
  value**. There is no string coercion: the string `"42"` does **not** match the
  number `42`, and a boolean does **not** match a number (`true` ≠ `1`,
  `false` ≠ `0`).
- The answer **also** matches if it is a string **exactly equal** to the choice's
  `name`.
- Disabled choices and separators never match.

## Separator Object Schema

```json
{"type": "separator", "text": "── Section ──"}
```

Separators are non-selectable visual dividers in choice lists. They are accepted
in this dict/object form at parse time everywhere, are never matchable, and are
filtered out of the `rawlist` payload and indexing (but included as separator
objects in `select`/`checkbox` payloads).

## Implementations

| Language | Package | Status |
|----------|---------|--------|
| Python | `inquirer-ai` (PyPI) | Complete — 12 prompt types, async support |
| Go | `github.com/sherlock49b/inquirer-ai/go/prompt` | Complete — 12 prompt types |
| TypeScript | `inquirer-ai` (npm) | Complete — 12 prompt types |
| Rust | `inquirer-ai` (crates.io) | Complete — 12 prompt types |

## Versioning

The protocol version follows semantic versioning. The `version` field in the handshake reflects the library version. Protocol-breaking changes increment the major version.
