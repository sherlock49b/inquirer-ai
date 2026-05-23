# inquirer-ai Agent Protocol Specification v1

## Overview

The inquirer-ai agent protocol enables AI agents to drive interactive CLI tools programmatically via a JSON Lines (JSONL) protocol on stdin/stdout. Programs built with inquirer-ai automatically support two modes:

- **Terminal mode**: Interactive UI with cursor navigation, key bindings, and styled output (default when stdin is a TTY)
- **Agent mode**: JSON line protocol on stdout/stdin (default when stdin is not a TTY, or `INQUIRER_AI_MODE=agent`)

## Mode Detection

Agent mode is activated when any of the following is true:

1. Environment variable `INQUIRER_AI_MODE` is set to `agent` (case-insensitive)
2. stdin is not a TTY (e.g., piped input)

Terminal mode is forced when `INQUIRER_AI_MODE` is set to `human`.

## Protocol Flow

```
Program                              Agent
  │                                    │
  ├──── handshake (1st line) ─────────►│
  │                                    │
  ├──── prompt (JSON line) ───────────►│
  │◄─── response (JSON line) ──────────┤
  │                                    │
  ├──── prompt (JSON line) ───────────►│
  │◄─── response (JSON line) ──────────┤
  │                                    │
  ├──── final output ─────────────────►│
  │                                    │
```

## Handshake

The first line emitted by the program is a handshake metadata object. It is sent exactly once, before the first prompt.

```json
{
  "protocol": "inquirer-ai",
  "version": "0.1.0",
  "format": "jsonl",
  "description": "Each prompt is a JSON line on stdout. Respond with a JSON line on stdin.",
  "example_response": {"answer": "<value>"}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `protocol` | string | Always `"inquirer-ai"` |
| `version` | string | Semantic version of the library |
| `format` | string | Always `"jsonl"` |
| `description` | string | Human-readable protocol description |
| `example_response` | object | Example of the expected response format |

Agents SHOULD check for `"protocol": "inquirer-ai"` in the first line to confirm the protocol is supported.

## Prompt Objects

Each prompt is a single JSON line with at minimum `type` and `message` fields:

```json
{"type": "<prompt_type>", "message": "<question text>", ...}
```

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Prompt type identifier |
| `message` | string | yes | The question to display |
| `default` | any | no | Default value if answer is null |

## Response Format

Every response MUST be a JSON object with an `answer` key:

```json
{"answer": <value>}
```

The value type depends on the prompt type. Sending `null` as the answer uses the prompt's default value.

## Prompt Types

### `input` — Text Input

```json
{"type": "input", "message": "What is your name?", "default": null}
```

**Response**: `{"answer": "Alice"}` → returns `"Alice"`
**Response**: `{"answer": null}` → returns default or `""`

---

### `confirm` — Yes/No

```json
{"type": "confirm", "message": "Continue?", "default": false}
```

**Response**: `{"answer": true}` or `{"answer": false}`
**Response**: `{"answer": "yes"}` → coerced to `true`

Accepted truthy strings: `y`, `yes`, `true`, `1`
Accepted falsy strings: `n`, `no`, `false`, `0`

---

### `select` — Single Choice

```json
{
  "type": "select",
  "message": "Pick a language",
  "default": null,
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
  "type": "checkbox",
  "message": "Select features",
  "default": ["docker"],
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
{"type": "password", "message": "Enter token", "default": null, "mask": "*"}
```

**Response**: `{"answer": "s3cret"}` → returns plain text

`mask` indicates the terminal display character. `null` means fully hidden. The agent receives and sends plain text regardless.

---

### `number` — Numeric Input

```json
{
  "type": "number",
  "message": "Port",
  "default": 8080,
  "min": 1024,
  "max": 65535,
  "float_allowed": false
}
```

**Response**: `{"answer": 3000}` — integer or float
**Response**: `{"answer": "3000"}` — string is parsed as number

Validation enforces min/max bounds and float_allowed constraint.

---

### `editor` — External Editor

```json
{"type": "editor", "message": "Enter description", "default": null, "postfix": ".txt"}
```

**Response**: `{"answer": "Multi-line\ntext content"}` → returns text string

In terminal mode, opens `$VISUAL` or `$EDITOR`. In agent mode, the agent provides the text directly.

---

### `search` — Searchable Selection

```json
{
  "type": "search",
  "message": "Find a package",
  "searchable": true,
  "choices": [
    {"name": "requests — HTTP client", "value": "requests"},
    {"name": "httpx — Async HTTP", "value": "httpx"}
  ]
}
```

**Response**: `{"answer": "httpx"}` — by value or name

The `choices` array contains the initial (unfiltered) results. The `searchable: true` field signals that this is a search prompt.

---

### `rawlist` — Numbered Selection

```json
{
  "type": "rawlist",
  "message": "Pick a version",
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
  "type": "expand",
  "message": "Conflict resolution",
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
{"type": "path", "message": "Output directory", "default": null, "only_directories": false}
```

**Response**: `{"answer": "/home/user/project"}` → returns path string

---

### `autocomplete` — Text with Suggestions

```json
{
  "type": "autocomplete",
  "message": "Language",
  "default": null,
  "choices": ["Python", "Go", "Rust", "TypeScript"]
}
```

**Response**: `{"answer": "Python"}` — any string accepted, not constrained to choices

The `choices` array provides suggestion hints. Agents MAY return values not in the list.

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

## Error Handling

### Malformed Input

| Condition | Error |
|-----------|-------|
| stdin closed (EOF) | `PromptAbortedError` — no response received |
| Invalid JSON | `ValidationError` — parse error with expected format hint |
| Missing `answer` key | `ValidationError` — must have `"answer"` key |
| Invalid choice value | `ValidationError` — value not in valid choices |
| Disabled choice selected | `ValidationError` — choice is disabled |
| Type mismatch | `ValidationError` — e.g., string instead of list for checkbox |

All error messages include the expected format to help agents self-correct:

```
Invalid JSON response: ... Expected JSON like: {"answer": "<value>"}
```

## Implementations

| Language | Package | Status |
|----------|---------|--------|
| Python | `inquirer-ai` (PyPI) | Complete — 12 prompt types, async support |
| Go | `github.com/sherlock49b/inquirer-ai/go/prompt` | Complete — 12 prompt types |

## Versioning

The protocol version follows semantic versioning. The `version` field in the handshake reflects the library version, not the protocol version. Protocol-breaking changes will be communicated via the `protocol` field format (e.g., `"inquirer-ai-v2"`).
