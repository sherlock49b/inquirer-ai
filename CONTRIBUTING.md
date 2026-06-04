# Contributing

## For Humans

### Prerequisites

- Python 3.10+
- Go 1.22+ (for the Go library)
- Node.js 18+ and npm (for the TypeScript library)
- Rust (stable toolchain) with `clippy` and `rustfmt` (for the Rust library) — `rustup component add clippy rustfmt`
- [uv](https://docs.astral.sh/uv/)
- [commitizen](https://commitizen-tools.github.io/commitizen/) with the [cz-agentic](https://github.com/sherlock49b/cz-agentic) plugin (`uv tool install commitizen --with ./python --with "git+https://github.com/sherlock49b/cz-agentic.git"`)

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

**TypeScript:**
```bash
cd typescript
npm ci                                 # Install dependencies
npx vitest run                         # Run tests
npx tsc --noEmit                       # Type check
npx biome check src/ tests/            # Lint + format check
```

**Rust:**
```bash
cd rust
cargo test                             # Run tests
cargo clippy -- -D warnings            # Lint
cargo fmt -- --check                   # Format check
```

### Committing

Use `cz commit` instead of `git commit`. This project uses the
[cz-agentic](https://github.com/sherlock49b/cz-agentic) commitizen plugin, which
extends Conventional Commits with structured decision-context fields:

```bash
cz commit
```

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `style`, `test`, `build`, `ci`, `chore`

Scope is free-form — use the most specific one (`python`, `go`, `spec`, `protocol`,
`compat`, a prompt type like `select`/`checkbox`, etc.). Whitespace in a scope is
hyphenated automatically.

Two fields are **required** on every commit and enforced by the `commit-msg` hook:

- `[tags]` — comma-separated retrieval keywords (specific terms, e.g. `handshake`, `socket-transport`).
- `[intent]` — why the change is necessary (the motivation, not the mechanism).

Optional fields (`[constraints]`, `[alternatives]`, `[uncertainty]`, `[refs]`) capture
decision context that isn't inferable from the diff — include them when they apply.
Run `cz info`, `cz example`, and `cz schema` to see the full convention.

> cz-agentic does not define the old `protocol`/`compat`/`hotfix` types. A protocol
> change is now e.g. `feat(protocol): …` / `fix(spec): …` with the protocol impact
> spelled out in `[intent]` (see *Protocol changes* below).

### Releasing

Releases are normally automated: pushing to `main` runs the `auto-bump` job in
`.github/workflows/release.yml`, which runs `cz bump` with the cz-agentic plugin
(installed from GitHub), regenerates `rust/Cargo.lock`, and pushes the bump commit +
tag. To bump manually (cz-agentic reads `[tool.commitizen]` in the root
`pyproject.toml`):

```bash
cz bump --yes --changelog   # Auto-determine version (feat/fix/refactor/perf, `!`/BREAKING CHANGE)
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

Run `cz commit`. In agent mode (non-TTY stdin), the tool auto-creates a Unix socket and writes the handshake (with socket path) to stdout. Each prompt is served on a separate socket connection.

```bash
# Start cz, capture handshake
INQUIRER_AI_MODE=agent cz commit > /tmp/handshake.txt &
SOCK=$(jq -r .socket /tmp/handshake.txt)

# Answer each prompt with an independent command, in order
echo '{"answer":"feat"}'                            | nc -U -q1 $SOCK  # type
echo '{"answer":"select"}'                          | nc -U -q1 $SOCK  # scope (free-form, enter to skip)
echo '{"answer":"show context on focused choice"}'  | nc -U -q1 $SOCK  # short description
echo '{"answer":""}'                                | nc -U -q1 $SOCK  # body (skip)
echo '{"answer":"select, choice-context, focus"}'   | nc -U -q1 $SOCK  # [tags]   (required)
echo '{"answer":"Users could not see per-choice context until selecting."}' | nc -U -q1 $SOCK  # [intent] (required)
echo '{"answer":""}'                                | nc -U -q1 $SOCK  # [constraints]
echo '{"answer":""}'                                | nc -U -q1 $SOCK  # [alternatives]
echo '{"answer":""}'                                | nc -U -q1 $SOCK  # [uncertainty]
echo '{"answer":""}'                                | nc -U -q1 $SOCK  # [refs]
echo '{"answer":false}'                             | nc -U -q1 $SOCK  # breaking change?
```

Each `nc` call connects, receives the prompt, sends the answer, and gets `{"status":"accepted"}`. No persistent session needed. The flow is **dynamic**: answering `true` to the breaking-change prompt adds one final prompt asking what breaks and how to migrate. Read each prompt before answering rather than assuming a fixed count; `[tags]` and `[intent]` reject empty answers.

### Commit question flow

`cz commit` walks these prompts in order (the last one appears only for breaking changes, so the count is 11 or 12):

| # | Type | Field | Valid answers |
|---|------|-------|---------------|
| 1 | select | Commit type | `feat`, `fix`, `refactor`, `perf`, `docs`, `style`, `test`, `build`, `ci`, `chore` |
| 2 | input | Scope | Free-form (`python`, `go`, `spec`, `select`, …), or empty to skip |
| 3 | input | Short description | Imperative mood, no period. **Required** |
| 4 | input | Body | Any text, or empty to skip |
| 5 | input | `[tags]` | Comma-separated retrieval keywords. **Required** |
| 6 | input | `[intent]` | Why the change is necessary. **Required** |
| 7 | input | `[constraints]` | Limitations not visible in the code, or empty to skip |
| 8 | input | `[alternatives]` | Rejected approaches + reasons, or empty to skip |
| 9 | input | `[uncertainty]` | Arbitrary values / temp solutions / unverified assumptions, or empty to skip |
| 10 | input | `[refs]` | Related commits (`hash — reason`), or empty to skip |
| 11 | confirm | Breaking change? | `true` or `false` |
| 12 | input | Breaking-change description | Only asked when #11 is `true`. What breaks + migration. **Required** |

### Choosing the right type

- `feat` — new prompt type, API, or user-facing capability
- `fix` — bug fix in prompt behavior, validation, or rendering
- `refactor` — restructuring without behavior change
- `perf` — performance improvement (no behavior change)
- `docs` — documentation, README, protocol spec
- `style` — formatting only (no code change)
- `test` — adding or improving tests
- `build` — build system or dependencies
- `ci` — CI/CD pipeline changes
- `chore` — other changes that don't touch src or tests

There is no dedicated `protocol`/`compat` type. For an agent-protocol or compat-layer
change, use the type that fits (`feat`/`fix`/`refactor`) with scope `protocol`, `spec`,
or `compat`, and spell out the impact in `[intent]`.

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

1. Use scope `protocol` (or `spec`) on a `feat`/`fix`/`refactor` commit, and describe the protocol impact in `[intent]`
2. Update `spec/protocol.md`
3. Update all 4 implementations: Python, Go, TypeScript, Rust
4. Ensure all tests pass in all languages

### Git hooks reference

| Hook | Runs | Blocks on failure? |
|------|------|:------------------------:|
| `commit-msg` | `cz check` — enforces the cz-agentic format, including required `[tags]`/`[intent]`; skips the `bump:` release commit | Yes |
| `pre-commit` | Python lint + typecheck + tests, Go fmt + vet + tests, TS tsc + biome + tests, Rust fmt + clippy + tests (only for changed languages, run sequentially) | Yes |
| `pre-push` | No-op — `pre-commit` already covers the changed languages and CI runs the full matrix | No |

### Code style

- **Python**: ruff format (120 chars), ruff lint, pyright strict mode, 80% coverage minimum
- **Go**: gofmt, go vet
- **TypeScript**: biome lint/format, tsc strict
- **Rust**: rustfmt, clippy, `#![deny(warnings)]`

### Example commit session (socket transport)

```bash
$ INQUIRER_AI_MODE=agent cz commit > /tmp/hs.txt &
$ SOCK=$(jq -r .socket /tmp/hs.txt)

$ echo '{"answer":"feat"}' | nc -U -q1 $SOCK
{"kind":"prompt","type":"select","message":"Select the type of change...","choices":[...]}
{"status":"accepted"}

$ echo '{"answer":"select"}' | nc -U -q1 $SOCK
{"kind":"prompt","type":"input","message":"Scope of this change (press enter to skip):"}
{"status":"accepted"}

$ echo '{"answer":"add context shown on focused choice"}' | nc -U -q1 $SOCK
{"kind":"prompt","type":"input","message":"Short description (imperative mood, no period, required):"}
{"status":"accepted"}

# ... body (skip), then the required [tags] and [intent], the optional fields, and the breaking-change confirm

# Result:
#   feat(select): add context shown on focused choice
#
#   [tags]
#   select, choice-context, focus
#
#   [intent]
#   Choices carried extra context that users could not see until selecting.
```
