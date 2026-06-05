# AGENTS.md

Entry point for AI coding agents. The **authoritative** guide is
[CONTRIBUTING.md → "For AI Agents"](CONTRIBUTING.md#for-ai-agents); this file is
the quick map so a fresh, stateless session can bootstrap from the repo alone.

## What this is

`inquirer-ai` — an interactive CLI prompt library that speaks two protocols from
one codebase: a terminal UI for humans and a JSON line protocol for agents.
Implemented in **four languages that must stay behavior-identical**: Python
(`python/`, the reference impl), TypeScript (`typescript/`), Go (`go/`), Rust
(`rust/`). The cross-language contract is `spec/protocol.md`, enforced by the
`conformance/` suite.

## Bootstrap (per language, from repo root)

```bash
cd python && uv sync --group dev            # Python
cd typescript && npm ci                     # TypeScript
cd go && go build ./...                     # Go
cd rust && cargo build                      # Rust
```

## Hard rules (non-negotiable — see CONTRIBUTING for the full list)

- **Work on branches; never push to `main` directly.** Every PR maps to a
  human-approved task. One PR per task; do not bundle unrelated changes.
- **Every agent action is backed by a human** who reviews before it lands.
- **Commit with `cz commit`** (the cz-agentic convention): `[tags]` and
  `[intent]` are required; the `commit-msg` hook runs `cz check` and rejects
  malformed messages. Install: see CONTRIBUTING "Prerequisites".
- **A protocol change touches all four languages + `spec/protocol.md` + the
  conformance suite**, or it is incomplete.

## The automated floor (what gates your change)

| Gate | Runs | Blocks |
|---|---|---|
| `commit-msg` hook | `cz check` (message format) | local commit |
| `pre-commit` hook | format + lint + typecheck + tests for the changed language(s) | local commit |
| CI (`.github/workflows/ci.yml`) | full 4-language matrix | merge |
| Conformance (`conformance.yml`) | cross-language protocol identity (stdio + socket) | merge |
| CodeQL (`codeql.yml`) | SAST for Python/TS/Go | (advisory → required) |
| Secret push protection | GitHub server-side | push |
| Dependabot (`dependabot.yml`) | weekly dep + security updates | (alerts) |

CI is authoritative — a green `pre-commit` is the fast local mirror, not the
final word. The `main` branch auto-publishes to npm/PyPI/crates on merge, so a
bad merge ships to real consumers: keep `main` releasable.

## Where knowledge lives

- `spec/protocol.md` — the wire contract. `spec/socket-transport.md` — the socket transport.
- `CONTRIBUTING.md` — full human + agent workflow, commit flow, prompt-by-prompt cz guide.
- `extensions/` — real tools built on inquirer-ai (gh-contribute, cz-ai, cargo-deps).
- Commit messages (cz-agentic `[intent]`/`[constraints]`) are the durable record of *why*.
