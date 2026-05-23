# Contributing

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# Clone the repo
git clone https://github.com/sherlock49b/inquirer-ai.git
cd inquirer-ai

# Install dependencies
cd python
uv sync --group dev

# Enable shared git hooks
cd ..
git config core.hooksPath .githooks
```

## Development workflow

```bash
cd python

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check (strict mode)
uv run pyright src/
```

## Git hooks

Shared hooks live in `.githooks/`:

- **pre-commit**: ruff check + format + pyright + quick tests
- **pre-push**: same + full test suite with coverage

## Code style

- **Formatter**: ruff format (120 char line length)
- **Linter**: ruff with E/W/F/I/UP/B/SIM/RUF rules
- **Type checker**: pyright strict mode
- **Coverage**: 80% minimum enforced by pytest

## Pull requests

- Use [conventional commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`)
- All CI checks must pass before merge
