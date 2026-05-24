# Extensions

Real-world tools built with inquirer-ai, demonstrating how the library enables AI agents to drive interactive CLIs.

## gh-contribute

A GitHub CLI extension for fork-based contribution workflows. Guides contributors through forking, branching, PR creation, and cleanup — all drivable by AI agents via the inquirer-ai JSON protocol.

```bash
# Install as gh extension
cd extensions/gh-contribute
go build -o gh-contribute .
mkdir -p ~/.local/share/gh/extensions/gh-contribute
cp gh-contribute ~/.local/share/gh/extensions/gh-contribute/

# Use
gh contribute
```

**Source:** [`extensions/gh-contribute/`](gh-contribute/)

## cz-teamcz

A custom commitizen plugin with project-specific commit types and scopes. Demonstrates how inquirer-ai's questionary compatibility layer lets custom plugins be driven by AI agents without any extra work.

Commit types: `feat`, `fix`, `protocol`, `compat`, `refactor`, `test`, `docs`, `chore`, `ci`

Scopes: `python`, `go`, `spec`, and individual prompt types (`select`, `checkbox`, etc.)

```bash
# Install: copy into commitizen's cz directory and register in __init__.py
# Configure in pyproject.toml:
[tool.commitizen]
name = "teamcz"
```

**Source:** [`extensions/cz-teamcz/`](cz-teamcz/)

## cz-inquirer-ai

A Node.js commitizen adapter powered by inquirer-ai's TypeScript library. Provides agent-protocol-aware conventional commits — any AI agent can drive the commit flow via the JSON line protocol without knowing your project's conventions in advance.

```bash
# Install
npm install --save-dev cz-inquirer-ai commitizen

# Configure in package.json:
{
  "config": {
    "commitizen": {
      "path": "cz-inquirer-ai"
    }
  }
}

# Use
npx cz
```

**Source:** [`extensions/cz-inquirer-ai/`](cz-inquirer-ai/)

## cargo-deps

A Cargo subcommand for interactive dependency management using inquirer-ai's Rust library. Search, add, and remove crates interactively — with full AI agent support via the inquirer-ai protocol.

```bash
# Install
cargo install --path extensions/cargo-deps

# Use
cargo deps
```

**Source:** [`extensions/cargo-deps/`](cargo-deps/)
