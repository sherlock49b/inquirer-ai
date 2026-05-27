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
  "version": "0.3.2",
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
| `INQUIRER_AI_MODE=agent` | Socket auto-created at `/tmp/inquirer-ai-{pid}.sock` |
| `INQUIRER_AI_SOCKET=/path` set | Socket created at specified path |
| Non-TTY stdin (piped) | Stdin/stdout (backwards compatible) |
| `INQUIRER_AI_MODE=human` | Terminal mode, no socket |

Socket is auto-created when `INQUIRER_AI_MODE=agent` is explicitly set. Piped stdin (`echo '...' | my-cli`) keeps the old stdin/stdout behavior for backwards compatibility. `INQUIRER_AI_SOCKET` overrides the auto-generated path.

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
3. Read one line from the client (the answer)
4. Validate:
   - **Valid**: write `{"status":"accepted"}\n`, close connection, advance to next prompt
   - **Invalid**: write `{"kind":"validation_error","message":"..."}\n`, read another line (retry, up to 3 total)
   - **Max retries exceeded**: write `{"kind":"error","message":"..."}\n`, close, program exits
5. If client disconnects before sending an answer: re-queue the prompt for the next connection (no error, no retry consumed)

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

1. **Startup**: CLI creates socket, writes handshake to stdout (with socket path), handshake also sent on first socket connection
2. **Running**: Accept connections, one per prompt cycle
3. **Shutdown**: Close socket, remove socket file. Handles SIGINT/SIGTERM gracefully (cleanup before exit)
4. **Crash**: Socket file may remain as stale. Next invocation detects and removes stale socket before binding.

## Implementation Notes

### Server threading model

The socket server runs on the **same thread** as the prompt logic, blocking between prompts. No background thread needed:

```
prompt_1() → accept() → send prompt → read answer → validate → return value
prompt_2() → accept() → send prompt → read answer → validate → return value
```

Each prompt function blocks on `accept()`. This naturally synchronizes prompt order with connection order.

### Cleanup

All 4 languages must implement: `atexit` handler + `SIGTERM` handler that remove the socket file.

## NOT in scope

- **TCP sockets**: Unix-only. Agents and CLIs are always co-located.
- **Concurrent connections**: One connection at a time. Prompts are sequential.
- **HTTP framing**: Raw JSONL over Unix socket. No HTTP overhead. `nc` and `socat` work directly.
- **Windows**: Named pipes are a separate concern for a future design.
