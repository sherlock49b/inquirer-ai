# inquirer-ai (Python)

Interactive CLI prompts for both humans and AI agents.

`inquirer-ai` is a Python library that provides Inquirer-style interactive prompts with a dual-mode design:

- **Human mode** -- renders a full terminal UI (arrow keys, checkboxes, etc.)
- **Agent mode** -- communicates via structured JSON over stdin/stdout, enabling AI agents to operate interactive CLIs

## Install

```bash
pip install inquirer-ai
```

Requires Python 3.10+.

## Quick Start

```python
from inquirer_ai import text, confirm, select, checkbox

name = text("What is your name?")
proceed = confirm("Continue?", default=True)
db = select("Choose database:", choices=["PostgreSQL", "MySQL", "SQLite"])
features = checkbox("Select features:", choices=["Auth", "Cache", "Logging"])
```

Or use the declarative API with `prompt()`:

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
# {"username": "Alice", "ok": True, "db": "PostgreSQL", "features": ["Auth"]}
```

---

## Prompt Types

### text

Free-form text input.

```python
def text(
    message: str,
    *,
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
    transformer: Callable[[str], str] | None = None,
) -> str
```

```python
from inquirer_ai import text

name = text("Your name:", default="World")
```

**Agent mode** -- sends `{"type": "input", "message": "Your name:", "default": "World"}`, expects `{"answer": "Alice"}`.

---

### confirm

Yes/no boolean prompt.

```python
def confirm(
    message: str,
    *,
    default: bool = False,
    validate: Callable[[bool], bool | str | None] | None = None,
    filter: Callable[[bool], bool] | None = None,
    transformer: Callable[[bool], str] | None = None,
) -> bool
```

```python
from inquirer_ai import confirm

ok = confirm("Deploy to production?", default=False)
```

**Agent mode** -- sends `{"type": "confirm", "message": "Deploy to production?", "default": false}`, expects `{"answer": true}`.

---

### select

Pick one item from a list. Supports arrow-key navigation in the terminal.

```python
def select(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any
```

```python
from inquirer_ai import select

db = select("Choose database:", choices=["PostgreSQL", "MySQL", "SQLite"])
```

**Agent mode** -- sends `{"type": "select", "message": "...", "choices": [...]}`, expects `{"answer": "PostgreSQL"}`.

---

### checkbox

Pick zero or more items from a list. Space to toggle, Enter to confirm.

```python
def checkbox(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: list[Any] | None = None,
    page_size: int = 10,
    validate: Callable[[list[Any]], bool | str | None] | None = None,
    filter: Callable[[list[Any]], list[Any]] | None = None,
) -> list[Any]
```

```python
from inquirer_ai import checkbox

features = checkbox(
    "Select features:",
    choices=["Auth", "Cache", "Logging", "Metrics"],
    validate=lambda v: True if len(v) >= 1 else "Pick at least one",
)
```

**Agent mode** -- expects `{"answer": ["Auth", "Cache"]}`.

---

### password

Masked text input. Characters are replaced with `mask` (default `*`), or hidden entirely with `mask=None`.

```python
def password(
    message: str,
    *,
    mask: str | None = "*",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str
```

```python
from inquirer_ai import password

secret = password("Enter API key:", mask=None)
```

**Agent mode** -- sends `{"type": "password", "message": "..."}`, expects `{"answer": "sk-..."}`.

---

### number

Numeric input with optional range and float control.

```python
def number(
    message: str,
    *,
    default: int | float | None = None,
    min: int | float | None = None,
    max: int | float | None = None,
    float_allowed: bool = True,
    validate: Callable[[int | float], bool | str | None] | None = None,
    filter: Callable[[int | float], int | float] | None = None,
) -> int | float
```

```python
from inquirer_ai import number

port = number("Port:", default=8080, min=1, max=65535, float_allowed=False)
```

**Agent mode** -- sends `{"type": "number", "message": "...", "min": 1, "max": 65535}`, expects `{"answer": 8080}`.

---

### editor

Opens the user's `$EDITOR` (or `vim`) for multi-line input. The edited content is returned as a string.

```python
def editor(
    message: str,
    *,
    default: str | None = None,
    postfix: str = ".txt",
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str
```

```python
from inquirer_ai import editor

commit_msg = editor("Commit message:", postfix=".md")
```

**Agent mode** -- sends `{"type": "editor", "message": "..."}`, expects `{"answer": "full text content..."}`.

---

### search

Dynamic list filtered by a user-typed query. The `source` callback receives the current input and returns matching choices.

```python
def search(
    message: str,
    *,
    source: Callable[[str], list[RawChoice]],
    page_size: int = 10,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any
```

```python
from inquirer_ai import search

CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]

city = search(
    "Search city:",
    source=lambda q: [c for c in CITIES if q.lower() in c.lower()],
)
```

**Agent mode** -- sends `{"type": "search", "message": "..."}`, expects `{"answer": "Chicago"}`.

---

### rawlist

Numbered list -- the user selects by typing the number.

```python
def rawlist(
    message: str,
    *,
    choices: Sequence[str | dict[str, Any] | Choice[Any]],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any
```

```python
from inquirer_ai import rawlist

action = rawlist(
    "Pick action:",
    choices=["Build", "Test", "Deploy", "Rollback"],
)
```

**Agent mode** -- sends `{"type": "rawlist", "message": "...", "choices": [...]}`, expects `{"answer": "Deploy"}`.

---

### expand

Compact prompt where each choice has a single-key shortcut. The user types the key letter to select.

```python
def expand(
    message: str,
    *,
    choices: list[dict[str, Any] | ExpandChoice],
    default: Any = None,
    validate: Callable[[Any], bool | str | None] | None = None,
    filter: Callable[[Any], Any] | None = None,
) -> Any
```

Each choice requires `key`, `name`, and `value`:

```python
from inquirer_ai import expand
from inquirer_ai.prompts.expand import ExpandChoice

action = expand(
    "Conflict on file.txt:",
    choices=[
        ExpandChoice(key="y", name="Overwrite", value="overwrite"),
        ExpandChoice(key="a", name="Overwrite all", value="overwrite_all"),
        ExpandChoice(key="d", name="Show diff", value="diff"),
        ExpandChoice(key="x", name="Abort", value="abort"),
    ],
)
```

**Agent mode** -- sends `{"type": "expand", "message": "...", "choices": [...]}`, expects `{"answer": "overwrite"}`.

---

### path

File/directory path input with tab-completion.

`PathPrompt` is available but does not yet have a top-level convenience function. Use the class directly:

```python
from inquirer_ai.prompts.path import PathPrompt

filepath = PathPrompt(
    "Config file:",
    default="~/.config/app.toml",
    only_directories=False,
    file_filter=lambda name: name.endswith(".toml"),
).execute()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default` | `str \| None` | `None` | Pre-filled path |
| `only_directories` | `bool` | `False` | Restrict completion to directories |
| `file_filter` | `Callable[[str], bool] \| None` | `None` | Filter which files appear in completion |
| `validate` | `Callable` | `None` | Validation callback |
| `filter` | `Callable` | `None` | Transform the answer |

**Agent mode** -- sends `{"type": "path", "message": "...", "only_directories": false}`, expects `{"answer": "/etc/app.toml"}`.

---

### autocomplete

Text input with word-completion from a fixed list.

```python
def autocomplete(
    message: str,
    *,
    choices: list[str],
    default: str | None = None,
    validate: Callable[[str], bool | str | None] | None = None,
    filter: Callable[[str], str] | None = None,
) -> str
```

```python
from inquirer_ai import autocomplete

lang = autocomplete(
    "Programming language:",
    choices=["Python", "Rust", "Go", "TypeScript", "Java", "C++"],
)
```

**Agent mode** -- sends `{"type": "autocomplete", "message": "...", "choices": [...]}`, expects `{"answer": "Rust"}`.

---

## Rich Choices

### Choice

For `select`, `checkbox`, `rawlist`, and other choice-based prompts, you can pass `Choice` objects instead of plain strings:

```python
from inquirer_ai import select, Choice

db = select(
    "Choose database:",
    choices=[
        Choice(name="PostgreSQL (recommended)", value="pg", description="ACID-compliant RDBMS"),
        Choice(name="MySQL", value="mysql"),
        Choice(name="SQLite (dev only)", value="sqlite", disabled="not for production"),
    ],
)
# Returns "pg", "mysql", or "sqlite"
```

**Choice fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Display text shown to the user |
| `value` | `V` | required | Value returned when selected |
| `disabled` | `bool \| str` | `False` | `True` or a reason string disables the choice |
| `short` | `str \| None` | `None` | Short label shown after selection |
| `description` | `str \| None` | `None` | Extra description shown beside the choice |

Choices can also be passed as dicts with the same keys:

```python
choices = [
    {"name": "PostgreSQL", "value": "pg", "description": "Production-ready"},
    {"name": "SQLite", "value": "sqlite", "disabled": "dev only"},
]
```

### Separator

Insert a visual divider between choices:

```python
from inquirer_ai import select, Separator

env = select(
    "Target environment:",
    choices=[
        "development",
        "staging",
        Separator("--- production ---"),
        "us-east-1",
        "eu-west-1",
    ],
)
```

`Separator(text="--------")` -- the `text` parameter customizes the divider line.

---

## Validation, Filter, Transformer

All prompts accept optional callbacks for validation, filtering, and display transformation.

### validate

Return `True` if the input is valid, or a string error message to reject it. In terminal mode, the prompt re-displays on failure. In agent mode, a `ValidationError` is raised.

```python
email = text(
    "Email address:",
    validate=lambda v: True if "@" in v else "Must contain @",
)
```

### filter

Transform the answer before returning it. Runs after validation.

```python
username = text(
    "Username:",
    filter=lambda v: v.strip().lower(),
)
```

### transformer

Transform the displayed value in the terminal (does not affect the returned value). Only available on `text` and `confirm`.

```python
token = text(
    "API token:",
    transformer=lambda v: v[:4] + "****" if len(v) > 4 else v,
)
```

### Combined example

```python
port = number(
    "Port number:",
    default=3000,
    min=1024,
    max=65535,
    validate=lambda v: True if v != 8080 else "8080 is reserved",
    filter=lambda v: int(v),
)
```

---

## Async Support

Every prompt has an async variant with an `_async` suffix. These return the same types but can be awaited:

```python
import asyncio
from inquirer_ai import text_async, select_async, confirm_async

async def main():
    name = await text_async("Your name:")
    db = await select_async("Database:", choices=["PostgreSQL", "MySQL"])
    ok = await confirm_async("Proceed?")

asyncio.run(main())
```

Full list of async functions:

| Sync | Async |
|------|-------|
| `text()` | `text_async()` |
| `confirm()` | `confirm_async()` |
| `select()` | `select_async()` |
| `checkbox()` | `checkbox_async()` |
| `password()` | `password_async()` |
| `number()` | `number_async()` |
| `editor()` | `editor_async()` |
| `search()` | `search_async()` |
| `rawlist()` | `rawlist_async()` |
| `expand()` | `expand_async()` |
| `autocomplete()` | `autocomplete_async()` |

---

## questionary Compatibility

A drop-in compatibility layer lets you replace `questionary` with `inquirer-ai` in projects like commitizen:

```python
# Replace:
#   import questionary
# With:
from inquirer_ai.compat import questionary

# All standard questionary patterns work:
name = questionary.text("Your name:", default="").ask()
ok = questionary.confirm("Continue?", default=True).ask()
db = questionary.select("Database:", choices=["PostgreSQL", "MySQL"]).ask()
features = questionary.checkbox("Features:", choices=["Auth", "Cache"]).ask()

# .unsafe_ask() raises on Ctrl+C instead of returning None:
name = questionary.text("Name:").unsafe_ask()

# questionary.prompt() batch interface:
answers = questionary.prompt([
    {"type": "input", "name": "user", "message": "Username:"},
    {"type": "confirm", "name": "ok", "message": "Proceed?"},
])
```

The compat layer also supports `questionary.Choice(title=..., value=..., checked=..., disabled=..., description=...)` and `async` via `.ask_async()` / `.unsafe_ask_async()`.

The `style` parameter is accepted but ignored -- use `set_theme()` for styling.

---

## Theming

Customize colors and symbols globally with the `Theme` dataclass:

```python
from inquirer_ai import set_theme, get_theme, Theme

set_theme(Theme(
    question="#61afef",
    success="#98c379",
    pointer="#c678dd",
    highlight="#61afef",
    selected="#98c379",
    answer="#56b6c2",
    error="#e06c75",
    muted="#5c6370",
    sym_question="?",
    sym_success="v",
    sym_pointer=">",
    sym_checked="[x]",
    sym_unchecked="[ ]",
))
```

**Theme fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question` | `str` | `"#9fa4e3"` | Color of the question mark |
| `success` | `str` | `"#62bfa1"` | Color of the success checkmark |
| `pointer` | `str` | `"#9c99ec"` | Color of the cursor pointer |
| `highlight` | `str` | `"#90bbe9"` | Color of the focused item |
| `selected` | `str` | `"#59bca4"` | Color of checked/selected items |
| `answer` | `str` | `"#9db9dd"` | Color of the submitted answer |
| `error` | `str` | `"#d77780"` | Color of error messages |
| `muted` | `str` | `"#84858f"` | Color of hints and disabled text |
| `sym_question` | `str` | `"?"` | Symbol before the question |
| `sym_success` | `str` | `"✓"` | Symbol after successful answer |
| `sym_pointer` | `str` | `"❯"` | Cursor pointer symbol |
| `sym_checked` | `str` | `"◉"` | Checked checkbox symbol |
| `sym_unchecked` | `str` | `"◯"` | Unchecked checkbox symbol |

All color values are hex strings. The theme is stored in a `ContextVar`, so it is safe to use in async / threaded contexts. Retrieve the current theme with `get_theme()`.

---

## Agent Protocol

Agent mode activates automatically when stdin is not a TTY (e.g., when called by an AI agent via a subprocess). You can also force it:

```bash
export INQUIRER_AI_MODE=agent
```

Each prompt writes one JSON line to **stdout**, then reads one JSON line from **stdin**.

**Prompt (stdout):**

```json
{"type": "select", "message": "Choose database:", "default": null, "choices": [{"name": "PostgreSQL", "value": "PostgreSQL"}, {"name": "MySQL", "value": "MySQL"}]}
```

**Response (stdin):**

```json
{"answer": "PostgreSQL"}
```

**Prompt types and answer formats:**

| Prompt Type | Agent `type` | Answer Format |
|-------------|-------------|---------------|
| `text` | `input` | `string` |
| `confirm` | `confirm` | `bool` |
| `select` | `select` | `string` (value or name) |
| `checkbox` | `checkbox` | `list[string]` |
| `password` | `password` | `string` |
| `number` | `number` | `number` |
| `editor` | `editor` | `string` |
| `search` | `search` | `string` |
| `rawlist` | `rawlist` | `string` |
| `expand` | `expand` | `string` |
| `path` | `path` | `string` |
| `autocomplete` | `autocomplete` | `string` |

For the full specification, see [spec/protocol.md](../spec/protocol.md).

---

## Error Handling

All exceptions inherit from `InquirerAIError`:

```
InquirerAIError
  +-- ValidationError
  |     +-- InvalidChoiceError
  +-- PromptAbortedError
  +-- EditorError
```

```python
from inquirer_ai import text
from inquirer_ai.exceptions import (
    InquirerAIError,
    ValidationError,
    InvalidChoiceError,
    PromptAbortedError,
    EditorError,
)

try:
    name = text("Name:")
except PromptAbortedError:
    print("User pressed Ctrl+C")
except ValidationError as e:
    print(f"Invalid input: {e}")
except EditorError as e:
    print(f"Editor failed: {e}")
except InquirerAIError as e:
    print(f"Prompt error: {e}")
```

| Exception | When |
|-----------|------|
| `InquirerAIError` | Base class for all library errors |
| `ValidationError` | A `validate` callback rejected the input |
| `InvalidChoiceError` | A choice value or dict is malformed |
| `PromptAbortedError` | The user pressed Ctrl+C |
| `EditorError` | The external editor process failed |

---

## Keyboard Shortcuts

### select

| Key | Action |
|-----|--------|
| Up / `k` | Move cursor up |
| Down / `j` | Move cursor down |
| Enter | Confirm selection |
| Ctrl+C | Abort |

### checkbox

| Key | Action |
|-----|--------|
| Up / `k` | Move cursor up |
| Down / `j` | Move cursor down |
| Space | Toggle current item |
| `a` | Toggle all items |
| Enter | Confirm selection |
| Ctrl+C | Abort |

---

## License

MIT
