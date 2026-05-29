# inquirer-ai Socket Transport

## Problem

The default stdin/stdout transport requires the agent to maintain a persistent bidirectional session with the CLI process. Agents like Claude Code and Codex execute bash commands as **independent, one-shot invocations** — they cannot interactively read from stdout, decide an answer, then write to stdin within a single command.

This makes the current protocol unusable for the most common agent runtimes.

## Solution

When agent mode is active, the CLI automatically creates a Unix domain socket and advertises its path in the handshake. Each socket connection handles exactly one prompt-answer cycle. Agents interact using independent bash commands (`nc -U` or `socat`), one per prompt.

## Discovery

The handshake — the first line on stdout — includes a `socket` field:

```json
{
  "kind": "handshake",
  "protocol": "inquirer-ai",
  "version": "0.3.1",
  "socket": "/tmp/inquirer-ai-29481.sock",
  "format": "jsonl",
  "interaction": "sequential",
  ...
}
```

The agent reads this single line from stdout and discovers the socket path. All subsequent interaction happens over the socket. **No environment variables required from the agent side.**

## Activation

| Condition | Transport |
|-----------|-----------|
| `INQUIRER_AI_MODE=agent` (case-insensitive) | Socket auto-created at `/tmp/inquirer-ai-{pid}.sock` |
| `INQUIRER_AI_SOCKET=/path` set (non-empty) — **even on a TTY** | Socket created at the specified path |
| Non-TTY stdin (piped), no MODE/SOCKET | Stdin/stdout (backwards compatible) |
| `INQUIRER_AI_MODE=human` | Terminal mode, no socket |
| `INQUIRER_AI_TRANSPORT=stdio` (with agent mode) | Forces stdin/stdout even when a socket is requested |

The socket transport is used when **socket_requested** (`INQUIRER_AI_SOCKET` set
and non-empty, **or** `INQUIRER_AI_MODE=agent`) is true, `INQUIRER_AI_TRANSPORT`
is not `stdio`, and Unix sockets are available. Setting `INQUIRER_AI_SOCKET`
activates the socket transport **even on a TTY**. Piped stdin
(`echo '...' | my-cli`) with no `INQUIRER_AI_MODE`/`INQUIRER_AI_SOCKET` keeps the
old stdin/stdout behavior for backwards compatibility. `INQUIRER_AI_SOCKET`
overrides the auto-generated path.

### `INQUIRER_AI_SOCKET` validation

When `INQUIRER_AI_SOCKET` is set it must be a non-empty **absolute** path, shorter
than 104 bytes (the `sun_path` limit), with an existing parent directory.
Otherwise the program refuses to start with a clear error.

## Connection Model

One connection = one prompt-answer cycle. The server accepts connections sequentially (one at a time).

### Per-connection flow

```
Agent                              CLI (socket server)
  │── connect ──────────────────►│
  │◄── prompt line(s) ───────────│  handshake (first conn only) + prompt
  │                               │  server now waits for answer
  │── {"answer": ...}\n ────────►│
  │◄── {"status":"accepted"}\n ──│  (or validation_error + retry loop)
  │── close ─────────────────────│
```

**Server behavior per connection:**

1. Accept connection
2. Write buffered lines: handshake (on first connection only) + current prompt, each as `\n`-terminated JSON
3. Read one line from the client (the answer). Each answer line is capped at
   `1_048_576` bytes; exceeding the cap is treated as a `validation_error`
   (consuming one attempt) and the server continues.
4. Validate (a single **unified budget of exactly 3 attempts** shared by
   type/coercion validation and any user `validate()` callback):
   - **Valid**: compute the result, write `{"status":"accepted"}\n` (suppressing
     a broken-pipe error on this write), close the connection, and advance to the
     next prompt **returning the already-computed result** (a failed `accepted`
     write must not lose the validated answer).
   - **Invalid (attempt 1 or 2)**: write `{"kind":"validation_error","message":"..."}\n`, read another line.
   - **Invalid (attempt 3)**: write `{"kind":"error","message":"..."}\n`, close, program exits non-zero.
5. If the client disconnects before sending an answer: re-queue the prompt for the
   next connection (no error, no retry consumed).

Parsing untrusted answer JSON MUST never crash the server: every parse/decoding
error (including recursion-depth and value errors) is caught and reported as a
`validation_error`. A non-`ValidationError` raised by a user `validate()`
callback is caught and reported as `{"kind":"error"}` before exit.

## Agent Usage

```bash
# 1. Start CLI — handshake is written to stdout
INQUIRER_AI_MODE=agent my-cli > /tmp/handshake.txt &

# 2. Parse socket path from handshake
SOCK=$(jq -r .socket /tmp/handshake.txt)

# 3. Answer prompts (each is an independent command)
echo '{"answer":"feat"}' | nc -U -q1 $SOCK
echo '{"answer":"add login"}' | nc -U -q1 $SOCK
echo '{"answer":true}' | nc -U -q1 $SOCK
```

### Peek (read-only)

Connect and disconnect without sending an answer. The server re-queues the prompt for the next connection.

```bash
nc -U -q0 $SOCK < /dev/null   # read prompt, don't answer
# Next connection gets the same prompt
echo '{"answer":"feat"}' | nc -U -q1 $SOCK
```

### Validation retry

Invalid answers get a `validation_error` response on the same connection. Send a corrected answer immediately:

```bash
# In a single nc session (via script):
printf '{"answer":80}\n{"answer":8080}\n' | nc -U -q1 $SOCK
# First answer invalid → validation_error
# Second answer accepted → accepted
```

## Dual handshake

The handshake is sent to **both** stdout and the first socket connection:

- **stdout**: For agent discovery — the agent reads the first line to find the socket path
- **First socket connection**: For agents that connect directly (e.g., when `INQUIRER_AI_SOCKET` is set explicitly)

## Protocol Messages

Socket transport reuses all existing message types from the JSONL protocol. One addition:

### `{"status":"accepted"}`

Sent by the server after a valid answer is received. Not present in the stdin/stdout transport (where the next prompt implicitly signals acceptance).

## Lifecycle

1. **Startup**: Before binding, `lstat` the target path (do **not** follow
   symlinks). If it exists and **is a socket**, unlink it (stale cleanup). If it
   exists and is **not** a socket (regular file, directory, or symlink), refuse
   to start with a clear error — never unlink a non-socket. A directory/permission
   error during removal is reported as a clean handled error, not a crash. After
   binding, `chmod` the socket to `0600`. Then write the handshake to stdout
   (with the socket path); the handshake is also sent on the first socket
   connection.
2. **Running**: Accept connections, one per prompt cycle.
3. **Shutdown**: Close the socket and remove the socket file on **SIGINT**,
   **SIGTERM**, and **normal exit**.
4. **Crash**: A socket file may remain stale. The next invocation detects it via
   `lstat` and removes it (only if it is a socket) before binding.

## Implementation Notes

### Server threading model

The socket server runs on the **same thread** as the prompt logic, blocking between prompts. No background thread needed:

```
prompt_1() → accept() → send prompt → read answer → validate → return value
prompt_2() → accept() → send prompt → read answer → validate → return value
```

Each prompt function blocks on `accept()`. This naturally synchronizes prompt order with connection order.

### Cleanup

All 4 languages must remove the socket file on **SIGINT**, **SIGTERM**, and
normal exit:

- **Python**: `atexit` handler plus replaced SIGINT & SIGTERM handlers; resetting
  the transport must `atexit.unregister` and restore the prior handlers, guarded
  by an idempotent `_cleaned_up` flag.
- **Rust**: SIGINT and SIGTERM handlers plus `atexit` (because `atexit` does not
  run on a default SIGINT).
- **TypeScript**: SIGINT and SIGTERM handlers plus the `'exit'` event (`'exit'`
  is not emitted on a signal).
- **Go**: handle both SIGINT and SIGTERM; `signal.Stop` the channel and stop the
  goroutine on `Cleanup()`/reset. Go has no `atexit`, so it exposes `Cleanup()`,
  which callers invoke via `defer`; normal-exit cleanup is the caller's
  responsibility.

The validation budget is a single unified counter of exactly 3 attempts per
prompt (at most 2 `validation_error` messages, then 1 fatal `error`), identical
to the stdio transport.

## NOT in scope

- **TCP sockets**: Unix-only. Agents and CLIs are always co-located.
- **Concurrent connections**: One connection at a time. Prompts are sequential.
- **HTTP framing**: Raw JSONL over Unix socket. No HTTP overhead. `nc` and `socat` work directly.
- **Windows**: Named pipes are a separate concern for a future design.
