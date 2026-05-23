# inquirer-ai

**One library. Two audiences. Zero friction.**

inquirer-ai is an interactive CLI prompt library that works for both humans and AI agents — out of the box. Build your CLI once, and it automatically speaks two languages: a rich terminal UI for humans, and a structured JSON protocol for AI agents.

No adapter. No wrapper. No "agent mode" bolted on as an afterthought.

## The Problem

Every interactive CLI today is a black box to AI agents. When an agent encounters a `[y/N]` prompt or an arrow-key menu, it has to resort to brittle hacks — simulating keystrokes, parsing ANSI escape codes, or asking the human to do it manually.

**inquirer-ai eliminates this entirely.** When stdin isn't a TTY, every prompt automatically switches to a self-describing JSON line protocol. The first line tells the agent exactly how to respond:

```json
{"protocol": "inquirer-ai", "version": "0.1.0", "format": "jsonl", "example_response": {"answer": "<value>"}}
```

The agent reads this once, and knows how to drive the entire CLI.

## Real-World Example: commitizen

[commitizen](https://github.com/commitizen-tools/commitizen) is a popular tool for writing standardized git commit messages. It asks 6 interactive questions — commit type, scope, description, etc.

We wrote a custom commitizen plugin with domain-specific commit types. But the real unlock wasn't the plugin — it was that **our AI agent could drive it with zero training**:

```
$ echo '{"answer":"feat"}
{"answer":"auth"}
{"answer":"add OAuth2 login flow"}
{"answer":""}
{"answer":false}
{"answer":""}' | cz commit
```

```
feat(auth): add OAuth2 login flow
Commit successful!
```

The agent didn't need documentation. It didn't need examples. The protocol handshake told it everything — what choices are available, what type each answer should be. Read, respond, done.

**What it took:** one line of code.

```diff
- import questionary
+ from inquirer_ai.compat import questionary
```

The rest of commitizen stays untouched. Every `questionary.select(...).ask()` call works exactly as before for humans, and now also works for agents.

## Install

```bash
pip install inquirer-ai    # Python
```

```bash
go get github.com/sherlock49b/inquirer-ai/go/prompt  # Go
```

## Quick Start

```python
import inquirer_ai

name = inquirer_ai.text("Project name?")
lang = inquirer_ai.select("Language?", choices=["Python", "Go", "Rust"])
features = inquirer_ai.checkbox("Features?", choices=["Docker", "CI/CD", "Tests"])
proceed = inquirer_ai.confirm("Create project?", default=True)
```

When a human runs this, they get arrow keys, colored output, and interactive menus.
When an AI agent runs it, they get JSON lines. Same code. Same behavior. Different interface.

## 12 Prompt Types

| Type | Human UI | Agent Response |
|------|----------|----------------|
| `text` | Free text input | `{"answer": "hello"}` |
| `confirm` | Y/n prompt | `{"answer": true}` |
| `select` | Arrow-key list | `{"answer": "value"}` |
| `checkbox` | Space to toggle | `{"answer": ["a","b"]}` |
| `password` | Masked input | `{"answer": "secret"}` |
| `number` | Numeric input | `{"answer": 42}` |
| `editor` | Opens $EDITOR | `{"answer": "long text"}` |
| `search` | Type to filter | `{"answer": "match"}` |
| `rawlist` | Type a number | `{"answer": 2}` |
| `expand` | Single key (y/n/a) | `{"answer": "y"}` |
| `path` | Tab completion | `{"answer": "/home/user"}` |
| `autocomplete` | Suggestions | `{"answer": "word"}` |

## Rich Choices

```python
from inquirer_ai import select, Choice, Separator

db = select("Database?", choices=[
    Choice("PostgreSQL", "pg", description="Relational, ACID compliant"),
    Choice("Redis", "redis", description="In-memory key-value"),
    Separator("── Experimental ──"),
    Choice("SurrealDB", "surreal", disabled="coming soon"),
])
```

## Validation, Filtering & Transformation

```python
port = inquirer_ai.number("Port?", min=1024, max=65535)

email = inquirer_ai.text(
    "Email?",
    validate=lambda v: "@" in v or "Invalid email",
    filter=lambda v: v.strip().lower(),
    transformer=lambda v: v.split("@")[0] + "@...",  # display only
)
```

## questionary Drop-in Replacement

For existing projects using [questionary](https://github.com/tmbo/questionary):

```python
from inquirer_ai.compat import questionary

# All existing code works unchanged:
questionary.select("Pick", choices=[...]).ask()
questionary.confirm("Sure?").unsafe_ask()
questionary.prompt(questions, style=style)
```

## Async Support

```python
name = await inquirer_ai.text_async("Name?")
db = await inquirer_ai.select_async("DB?", choices=["pg", "mysql"])
```

## Agent Protocol

Full specification: [`spec/protocol.md`](spec/protocol.md)

```
Program                              Agent
  │                                    │
  ├──── handshake ────────────────────►│  protocol metadata (once)
  ├──── {"type":"select",...} ────────►│  prompt
  │◄─── {"answer":"value"} ───────────┤  response
  ├──── {"type":"confirm",...} ───────►│  prompt
  │◄─── {"answer":true} ──────────────┤  response
  └────────────────────────────────────│
```

Auto-detection: non-TTY stdin → agent mode. Override: `INQUIRER_AI_MODE=agent|human`.

## Implementations

| | Python | Go |
|---|---|---|
| Prompt types | 12 | 12 |
| Terminal UI | prompt_toolkit | bubbletea + lipgloss |
| Agent protocol | JSONL | Same JSONL |
| Tests | 209 | 50 |
| Async | `*_async()` | goroutines |

Both implementations share the same protocol spec. An agent that learns from one can drive the other.

## License

MIT
