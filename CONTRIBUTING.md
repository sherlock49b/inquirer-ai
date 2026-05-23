# Contributing

## Prerequisites

- Python 3.10+
- Go 1.22+ (for Go library)
- [uv](https://docs.astral.sh/uv/)
- [commitizen](https://commitizen-tools.github.io/commitizen/) (`uv tool install commitizen`)

## Setup

```bash
# Clone the repo
git clone https://github.com/sherlock49b/inquirer-ai.git
cd inquirer-ai

# Install Python dependencies
cd python
uv sync --group dev

# Enable shared git hooks
cd ..
git config core.hooksPath .githooks
```

## Committing

This project uses a **custom commitizen plugin** (`teamcz`) with project-specific commit types and scopes. Use `cz commit` instead of `git commit`:

```bash
cz commit
```

It will guide you through:
1. **Type** — `feat`, `fix`, `protocol`, `compat`, `refactor`, `test`, `docs`, `chore`, `ci`
2. **Scope** — `python`, `go`, `spec`, or a specific prompt type (`select`, `checkbox`, etc.)
3. **Subject** — imperative summary
4. **Body** — context (optional)
5. **Breaking change** — protocol-breaking changes affect all agent consumers
6. **References** — issues, PRs (optional)

The `commit-msg` hook validates all commit messages against the teamcz schema — malformed commits are rejected.

### Example commits

```
feat(search): add dynamic filtering with source callback
fix(go): use json.Marshal in Separator.MarshalJSON to prevent injection
protocol(spec): add editor prompt type to protocol v1
compat(python): add unsafe_ask() to questionary compatibility layer
chore(ci): add Go to CI pipeline and git hooks
```

## Development workflow

### Python

```bash
cd python

uv run pytest                          # Run tests
uv run ruff check src/ tests/          # Lint
uv run ruff format src/ tests/         # Format
uv run pyright src/                    # Type check (strict)
```

### Go

```bash
cd go

go test ./prompt/ -v -cover            # Run tests
go vet ./prompt/ ./examples/...        # Vet
gofmt -l ./prompt/ ./examples/         # Format check
```

## Git hooks

Shared hooks in `.githooks/`:

| Hook | What it checks |
|------|---------------|
| **commit-msg** | `cz check` — commit message format |
| **pre-commit** | Python: ruff + pyright + pytest. Go: gofmt + vet + test |
| **pre-push** | Same as pre-commit + full coverage report |

## Releasing

```bash
cz bump              # Auto-determine next version from commits
cz changelog          # Regenerate CHANGELOG.md
git push --follow-tags
```

`cz bump` reads commit history, determines the version increment (MAJOR/MINOR/PATCH), updates version in `python/pyproject.toml` and `go/prompt/agent.go`, creates a tag, and generates changelog.

## Code style

- **Python**: ruff format (120 chars), ruff lint (E/W/F/I/UP/B/SIM/RUF), pyright strict, 80% coverage minimum
- **Go**: gofmt, go vet, golangci-lint config in `go/.golangci.yml`

## Pull requests

- Use `cz commit` for all commits
- All CI checks must pass (Python 3.10-3.13, Go 1.22-1.23)
- Protocol changes require `protocol` commit type and spec update
