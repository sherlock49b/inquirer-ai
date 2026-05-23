# inquirer-ai (Python)

Interactive CLI prompts for both humans and AI agents.

`inquirer-ai` is a Python library that provides Inquirer-style interactive prompts with a dual-mode design:

- **Human mode** — renders a full terminal UI (arrow keys, checkboxes, etc.)
- **Agent mode** — communicates via structured JSON over stdin/stdout, enabling AI agents to operate interactive CLIs

## Install

```bash
pip install inquirer-ai
```

## Quick Start

### Functional API

```python
from inquirer_ai import text, confirm, select, checkbox

name = text("What is your name?")
proceed = confirm("Continue?", default=True)
db = select("Choose database:", choices=["PostgreSQL", "MySQL", "SQLite"])
features = checkbox("Select features:", choices=["Auth", "Cache", "Logging"])
```

### Declarative API

```python
from inquirer_ai import prompt

questions = [
    {"type": "input", "name": "username", "message": "Enter your name:"},
    {"type": "confirm", "name": "ok", "message": "Proceed?"},
    {
        "type": "select",
        "name": "db",
        "message": "Choose database:",
        "choices": ["PostgreSQL", "MySQL", "SQLite"],
    },
    {
        "type": "checkbox",
        "name": "features",
        "message": "Select features:",
        "choices": ["Auth", "Cache", "Logging"],
    },
]

answers = prompt(questions)
# answers = {"username": "Alice", "ok": True, "db": "PostgreSQL", "features": ["Auth"]}
```

## Agent Mode

Agent mode activates automatically when stdin is not a TTY (e.g., when called by an AI agent via a subprocess). You can also force it with an environment variable:

```bash
export INQUIRER_AI_MODE=agent
```

### Protocol

Each prompt writes one JSON line to stdout, then reads one JSON line from stdin.

**Prompt (stdout):**

```json
{"type": "select", "message": "Choose database:", "default": null, "choices": [{"name": "PostgreSQL", "value": "PostgreSQL"}, {"name": "MySQL", "value": "MySQL"}]}
```

**Response (stdin):**

```json
{"answer": "PostgreSQL"}
```

### Prompt Types

| Type | Answer Format | Example |
|------|--------------|---------|
| `input` | `string` | `{"answer": "Alice"}` |
| `confirm` | `bool` | `{"answer": true}` |
| `select` | `string` (value or name) | `{"answer": "PostgreSQL"}` |
| `checkbox` | `list[string]` | `{"answer": ["Auth", "Cache"]}` |

## Validation & Filtering

All prompts accept optional `validate` and `filter` callbacks:

```python
email = text(
    "Email address:",
    validate=lambda v: True if "@" in v else "Must be a valid email",
    filter=lambda v: v.strip().lower(),
)

features = checkbox(
    "Select features:",
    choices=["Auth", "DB", "Cache"],
    validate=lambda v: True if len(v) >= 1 else "Select at least one",
)
```

- `validate` — return `True` for valid, or a string error message. In terminal mode, the prompt re-displays on failure.
- `filter` — transform the answer before returning it.

## Keyboard Shortcuts

### select

| Key | Action |
|-----|--------|
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `Enter` | Confirm selection |
| `Ctrl+C` | Abort |

### checkbox

| Key | Action |
|-----|--------|
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `Space` | Toggle current item |
| `a` | Toggle all items |
| `Enter` | Confirm selection |
| `Ctrl+C` | Abort |

## Rich Choices

Choices can be strings or objects with `name`/`value`:

```python
db = select(
    "Choose database:",
    choices=[
        {"name": "PostgreSQL (recommended)", "value": "pg"},
        {"name": "MySQL", "value": "mysql"},
        {"name": "SQLite (dev only)", "value": "sqlite"},
    ],
)
# Returns "pg", "mysql", or "sqlite"
```

## Theming

Customize colors and symbols:

```python
from inquirer_ai import set_theme, Theme

set_theme(Theme(
    question="#61afef",
    success="#98c379",
    sym_pointer=">",
    sym_checked="[x]",
    sym_unchecked="[ ]",
))
```

## License

MIT
