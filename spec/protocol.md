# inquirer-ai Agent Protocol Specification v2.1

## Overview

The inquirer-ai agent protocol enables AI agents to drive interactive CLI tools programmatically via a JSON Lines (JSONL) protocol. Programs built with inquirer-ai automatically support two modes:

- **Terminal mode**: Interactive UI with cursor navigation, key bindings, and styled output (default when stdin is a TTY)
- **Agent mode**: JSON line protocol for structured communication (default when stdin is not a TTY, or `INQUIRER_AI_MODE=agent`)

## Mode Detection

Agent mode is activated when any of the following is true:

1. Environment variable `INQUIRER_AI_MODE` is set to `agent` (case-insensitive)
2. stdin is not a TTY (e.g., piped input)

Terminal mode is forced when `INQUIRER_AI_MODE` is set to `human`.

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
  "version": "0.3.1",
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

When the agent sends an invalid answer, the tool sends a `validation_error` message followed by the same prompt again. The agent SHOULD retry with a corrected answer.

```json
{"kind": "validation_error", "message": "Invalid choice: 'java'. Valid: [\"python\", \"go\"]"}
```

The tool retries up to 3 times. After 3 failed attempts, the tool exits with a non-zero status.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | Always `"validation_error"` |
| `message` | string | yes | Human-readable error description |

## Fatal Error

For unrecoverable errors (e.g., stdin closed mid-prompt):

```json
{"kind": "error", "message": "stdin closed unexpectedly"}
```

The program exits with a non-zero status after emitting this message.

## Prompt Types

### `input` — Text Input

```json
{"kind": "prompt", "type": "input", "message": "What is your name?", "default": null, "step": 1, "total": 3}
```

**Response**: `{"answer": "Alice"}` → returns `"Alice"`
**Response**: `{"answer": null}` → returns default or `""`

---

### `confirm` — Yes/No

```json
{"kind": "prompt", "type": "confirm", "message": "Continue?", "default": false, "step": 2, "total": 3}
```

**Response**: `{"answer": true}` or `{"answer": false}`
**Response**: `{"answer": "yes"}` → coerced to `true`

Accepted truthy strings: `y`, `yes`, `true`, `1`
Accepted falsy strings: `n`, `no`, `false`, `0`

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

Disabled choices are rejected. Separators are non-selectable display elements.

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

**Response**: `{"answer": ["docker", "tests"]}` — array of values or names

---

### `password` — Masked Input

```json
{"kind": "prompt", "type": "password", "message": "Enter token", "default": null, "mask": "*", "step": 1, "total": 1}
```

**Response**: `{"answer": "s3cret"}` → returns plain text

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
**Response**: `{"answer": "3000"}` — string is parsed as number

Validation enforces min/max bounds and float_allowed constraint.

---

### `editor` — External Editor

```json
{"kind": "prompt", "type": "editor", "message": "Enter description", "default": null, "postfix": ".txt", "step": 1, "total": 1}
```

**Response**: `{"answer": "Multi-line\ntext content"}` → returns text string

In terminal mode, opens `$VISUAL` or `$EDITOR`. In agent mode, the agent provides the text directly.

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

The `choices` array contains the initial (unfiltered) results.

---

### `rawlist` — Numbered Selection

```json
{
  "kind": "prompt",
  "type": "rawlist",
  "message": "Pick a version",
  "step": 1,
  "total": 1,
  "choices": [
    {"name": "3.13", "value": "3.13"},
    {"name": "3.12", "value": "3.12"}
  ]
}
```

**Response**: `{"answer": 1}` — by 1-based index
**Response**: `{"answer": "3.13"}` — by value or name

---

### `expand` — Key-based Selection

```json
{
  "kind": "prompt",
  "type": "expand",
  "message": "Conflict resolution",
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

---

### `path` — File/Directory Path

```json
{"kind": "prompt", "type": "path", "message": "Output directory", "default": null, "only_directories": false, "step": 1, "total": 1}
```

**Response**: `{"answer": "/home/user/project"}` → returns path string

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

**Response**: `{"answer": "Python"}` — any string accepted, not constrained to choices

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
| `value` | any | yes | Value returned when selected |
| `disabled` | bool \| string | no | `true` or reason string to disable |
| `short` | string | no | Abbreviated display after selection |
| `description` | string | no | Context shown when choice is focused |

## Separator Object Schema

```json
{"type": "separator", "text": "── Section ──"}
```

Separators are non-selectable visual dividers in choice lists.

## Implementations

| Language | Package | Status |
|----------|---------|--------|
| Python | `inquirer-ai` (PyPI) | Complete — 12 prompt types, async support |
| Go | `github.com/sherlock49b/inquirer-ai/go/prompt` | Complete — 12 prompt types |
| TypeScript | `inquirer-ai` (npm) | Complete — 12 prompt types |
| Rust | `inquirer-ai` (crates.io) | Complete — 12 prompt types |

## Versioning

The protocol version follows semantic versioning. The `version` field in the handshake reflects the library version. Protocol-breaking changes increment the major version.
