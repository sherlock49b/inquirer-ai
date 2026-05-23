# Contributing

## For Humans

### Prerequisites

- Python 3.10+
- Go 1.22+ (for Go library)
- [uv](https://docs.astral.sh/uv/)
- [commitizen](https://commitizen-tools.github.io/commitizen/) (`uv tool install commitizen`)

### Setup

```bash
git clone https://github.com/sherlock49b/inquirer-ai.git
cd inquirer-ai

cd python && uv sync --group dev && cd ..
git config core.hooksPath .githooks
```

### Development workflow

**Python:**
```bash
cd python
uv run pytest                          # Run tests
uv run ruff check src/ tests/          # Lint
uv run ruff format src/ tests/         # Format
uv run pyright src/                    # Type check (strict)
```

**Go:**
```bash
cd go
go test ./prompt/ -v -cover            # Run tests
go vet ./prompt/ ./examples/...        # Vet
gofmt -l ./prompt/ ./examples/         # Format check
```

### Committing

Use `cz commit` instead of `git commit`. This project uses a custom commitizen plugin (`teamcz`) with project-specific types and scopes:

```bash
cz commit
```

Types: `feat`, `fix`, `protocol`, `compat`, `refactor`, `test`, `docs`, `chore`, `ci`

Scopes: `python`, `go`, `spec`, or a specific prompt type (`select`, `checkbox`, `compat`, etc.)

The `commit-msg` hook rejects malformed commit messages.

### Releasing

```bash
cz bump                # Auto-determine version from commit history
git push --follow-tags
```

---

## For AI Agents

This project uses `inquirer-ai` to power its own commit workflow. If you are an AI agent contributing to this repository, here is everything you need to know.

### Ground rules

**We welcome and encourage AI-assisted contributions.** AI agents are effective contributors when paired with a human who takes responsibility for their output. The principle is simple: **every action an AI agent takes must be backed by a human.**

**Human accountability:**

- Every issue, PR, and comment created by an AI agent must have a human who stands behind it. If you are an AI agent acting autonomously without human oversight, stop — this project does not accept unattended contributions.
- The human operating the agent is responsible for reviewing the agent's output before it reaches the repository. "The AI did it" is not an excuse for low-quality work.

**Behavioral constraints:**

- **Issues**: Do not create issues on your own initiative. Report findings to your human operator and let them decide whether to file.
- **Pull requests**: Every PR must correspond to a task approved by a human maintainer. Unsolicited PRs will be closed.
- **Comments**: Do not comment on existing issues or PRs unless explicitly asked to review. No drive-by suggestions.
- **Push access**: Work on branches, never push to `main` directly.
- **Scope**: One PR per task. Do not bundle unrelated changes or "clean up" code you were not asked to touch.
- **Rate limiting**: Do not create more than one issue or PR per task. If CI fails, fix and retry on the same PR — do not open new ones.
- **Closed items**: Do not re-open closed issues or PRs. Discuss with your human operator first.

These constraints exist not because we distrust AI, but because unattended agents can unintentionally generate a high volume of activity that drowns out real work. A human in the loop prevents this.

### Making commits

Run `cz commit` in agent mode. The tool will send prompts as JSON lines on stdout. Respond with `{"answer": <value>}` on stdin, **one at a time**.

**Use a named pipe for bidirectional I/O:**

```bash
mkfifo /tmp/cz_pipe
cz commit < /tmp/cz_pipe > /tmp/cz_out 2>&1 &
```

Then read one prompt from `/tmp/cz_out`, write one answer to `/tmp/cz_pipe`, repeat.

**Or batch if the questions are predictable:**

```bash
printf '{"answer":"feat"}\n{"answer":"python"}\n{"answer":"add X"}\n{"answer":""}\n{"answer":false}\n{"answer":""}\n' | cz commit
```

### Commit question flow

`cz commit` asks 6 questions in order:

| # | Type | Question | Valid answers |
|---|------|----------|---------------|
| 1 | select | Commit type | `feat`, `fix`, `protocol`, `compat`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci` |
| 2 | select | Scope | `python`, `go`, `spec`, `prompt`, `choice`, `theme`, `select`, `checkbox`, `text`, `confirm`, `password`, `number`, `editor`, `search`, `expand`, `rawlist`, `path`, `autocomplete`, `compat`, `ci`, `deps` |
| 3 | input | Short summary | Imperative mood, no period |
| 4 | input | Context (optional) | Any text, or empty string to skip |
| 5 | confirm | Breaking change? | `true` or `false` |
| 6 | input | References (optional) | Issue/PR numbers, or empty to skip |

### Choosing the right type

- `feat` — new prompt type, API, or user-facing capability
- `fix` — bug fix in prompt behavior, validation, or rendering
- `protocol` — change to the agent JSON protocol (handshake, prompt format, response schema). Use sparingly — this affects all consumers
- `compat` — changes to the `questionary` compatibility layer
- `refactor` — restructuring without behavior change
- `test` — adding or improving tests
- `docs` — documentation, README, protocol spec
- `chore` — build, CI, tooling, dependencies
- `ci` — CI/CD pipeline changes

### Choosing the right scope

Use the most specific scope that matches your change:
- Changing `select.py`? → `select`
- Changing both Python and Go agent protocol? → `spec`
- Adding a dependency? → `deps`
- Changing CI workflow? → `ci`
- Changing `compat/questionary.py`? → `compat`

### Running tests before committing

The pre-commit hook will run these automatically, but you can run them yourself:

```bash
cd python && uv run pytest tests/ -q && cd ..
cd go && go test ./prompt/ -count=1 && cd ..
```

### Protocol changes

If you change the agent JSON protocol (handshake format, prompt fields, response schema), you MUST:

1. Use commit type `protocol`
2. Update `spec/protocol.md`
3. Update both Python (`prompts/base.py`) and Go (`prompt/agent.go`) implementations
4. Ensure all tests pass in both languages

### Git hooks reference

| Hook | Runs | Blocks commit on failure? |
|------|------|:------------------------:|
| `commit-msg` | `cz check` (message format) | Yes |
| `pre-commit` | Python lint + typecheck + tests, Go fmt + vet + tests | Yes |
| `pre-push` | Same as pre-commit + coverage report | Yes |

### Code style

- **Python**: ruff format (120 chars), ruff lint, pyright strict mode, 80% coverage minimum
- **Go**: gofmt, go vet, golangci-lint

### Example commit session

```
$ cz commit

→ {"type":"select","message":"Select the type of change you are committing","choices":[{"name":"feat: A new prompt type...","value":"feat"},...]}
← {"answer":"feat"}

→ {"type":"select","message":"What part of the project is affected?","choices":[{"name":"python: Python library","value":"python"},...]}
← {"answer":"select"}

→ {"type":"input","message":"Write a short summary..."}
← {"answer":"add description shown on focused choice"}

→ {"type":"input","message":"Why is this change needed?..."}
← {"answer":""}

→ {"type":"confirm","message":"Is this a BREAKING CHANGE?...","default":false}
← {"answer":false}

→ {"type":"input","message":"References..."}
← {"answer":"#42"}

Result: feat(select): add description shown on focused choice
```
