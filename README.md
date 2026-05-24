# inquirer-ai

**One library. Two audiences. Zero friction.**

inquirer-ai is an interactive CLI prompt library that works for both humans and AI agents — out of the box. Build your CLI once, and it automatically speaks two languages: a rich terminal UI for humans, and a structured JSON protocol for AI agents.

No adapter. No wrapper. No "agent mode" bolted on as an afterthought.

## The Problem

Every interactive CLI today is a black box to AI agents. When an agent encounters a `[y/N]` prompt or an arrow-key menu, it has to resort to brittle hacks — simulating keystrokes, parsing ANSI escape codes, or asking the human to do it manually.

**inquirer-ai eliminates this entirely.** When stdin isn't a TTY, every prompt automatically switches to a self-describing JSON line protocol. The first line tells the agent exactly how to respond:

```json
{"protocol": "inquirer-ai", "version": "0.2.1", "format": "jsonl", "example_response": {"answer": "<value>"}}
```

The agent reads this once, and knows how to drive the entire CLI.

## Real-World Example: Custom commitizen Plugin

[commitizen](https://github.com/commitizen-tools/commitizen) is a popular tool for standardized commit messages. Every AI agent already knows how to use the default `cz commit` — it's in their training data.

But what happens when your team writes a **custom commitizen plugin** with domain-specific commit types, custom scopes, and internal conventions? The agent has never seen your plugin before. It's not in any documentation, any training set, or any example.

With inquirer-ai, that doesn't matter.

We built a custom commitizen plugin for our team. It has proprietary commit types (`infra`, `data-migration`, `rollback`), enforced scope naming, and a multi-step approval flow. None of this exists anywhere on the internet.

An AI agent ran it for the first time and immediately produced:

```
infra(k8s): migrate Redis cluster to new availability zone

BREAKING CHANGE: connection strings updated
Closes: OPS-4521
```

**The agent didn't need documentation. It didn't need examples. It had never seen our plugin before.** The protocol handshake told it everything — what commit types are available, what scopes are valid, what each field means. The choices themselves are the documentation.

```json
{"type": "select", "message": "Select commit type", "choices": [
  {"name": "infra: Infrastructure and deployment changes", "value": "infra"},
  {"name": "data-migration: Database schema or data changes", "value": "data-migration"},
  {"name": "rollback: Revert a previous release", "value": "rollback"}, ...
]}
```

Read the choices, pick one, send `{"answer": "infra"}`. Next prompt. Done.

This is the core idea: **any interactive CLI built with inquirer-ai is automatically operable by AI agents, even if the agent has never encountered it before.** The protocol is the documentation.

### How It Works

commitizen uses [questionary](https://github.com/tmbo/questionary) for its prompts. inquirer-ai provides a drop-in compatibility layer:

```diff
- import questionary
+ from inquirer_ai.compat import questionary
```

One line. The rest of commitizen — and your custom plugin — stays untouched. Every `questionary.select(...).ask()` call works exactly as before for humans, and now also works for agents.

## Real-World Example: gh-contribute

We built a GitHub CLI extension that guides contributors through the fork-based workflow — forking, branching, creating PRs, syncing, and cleanup. It uses inquirer-ai's Go library.

```
$ gh contribute

? What would you like to do?
  ❯ Start a new contribution    (Fork + branch from upstream/main)
    Create a PR from current branch
    Sync fork with upstream
    Clean up after merge

? Branch type?
  ❯ feat — new feature

? Short description: add-oauth-support

→ Branch 'feat/add-oauth-support' created from upstream/main.
```

An AI agent runs the same extension, sees JSON prompts, and drives the entire workflow without knowing anything about git commands:

```json
{"type": "select", "message": "What would you like to do?", "choices": [
  {"name": "Start a new contribution", "value": "new"},
  {"name": "Create a PR from current branch", "value": "pr"}, ...
]}
```

The agent doesn't need to know `git checkout -b`, `git push -u origin`, or `gh pr create --repo`. It just answers questions.

**Source:** [`extensions/gh-contribute/`](extensions/gh-contribute/)

## Install

```bash
pip install inquirer-ai    # Python
```

```bash
go get github.com/sherlock49b/inquirer-ai/go/prompt  # Go
```

```bash
npm install inquirer-ai    # TypeScript / Node.js
```

```bash
cargo add inquirer-ai      # Rust (crates.io)
# or as a git dependency in Cargo.toml:
# inquirer-ai = { git = "https://github.com/sherlock49b/inquirer-ai", subdirectory = "rust" }
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

**TypeScript:**

```typescript
import { text, select, checkbox, confirm } from "inquirer-ai";

const name = await text({ message: "Project name?" });
const lang = await select({ message: "Language?", choices: ["Python", "Go", "Rust"] });
const features = await checkbox({ message: "Features?", choices: ["Docker", "CI/CD", "Tests"] });
const proceed = await confirm({ message: "Create project?", default: true });
```

**Rust:**

```rust
use inquirer_ai::*;

let name = text(TextConfig { message: "Project name?".into(), ..Default::default() })?;
let lang = select(SelectConfig {
    message: "Language?".into(),
    choices: vec!["Python".into(), "Go".into(), "Rust".into()],
    ..Default::default()
})?;
let proceed = confirm(ConfirmConfig { message: "Create project?".into(), ..Default::default() })?;
```

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
  ├──── {"type":"select",...} ────────►│  prompt (includes kind, step/total)
  │◄─── {"answer":"value"} ───────────┤  response
  ├──── {"type":"confirm",...} ───────►│  prompt
  │◄─── {"answer":true} ──────────────┤  response
  │     (validation error?)            │
  ├──── {"error":"invalid"} ─────────►│  validation retry
  │◄─── {"answer":"fixed"} ───────────┤  corrected response
  └────────────────────────────────────│
```

v2 features: `kind` field for prompt semantics, `step`/`total` for progress tracking, validation retry loop.

Auto-detection: non-TTY stdin → agent mode. Override: `INQUIRER_AI_MODE=agent|human`.

## Implementations

| | Python | Go | TypeScript | Rust |
|---|---|---|---|---|
| Prompt types | 12 | 12 | 12 | 12 |
| Terminal UI | prompt_toolkit | bubbletea + lipgloss | ink | crossterm |
| Agent protocol | JSONL | Same JSONL | Same JSONL | Same JSONL |
| Tests | 297 | ~130 | 128 | 108 |
| Async | `*_async()` | goroutines | native async/await | tokio |

All implementations share the same protocol spec. An agent that learns from one can drive any of the others.

## License

MIT
