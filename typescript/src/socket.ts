import * as fs from "node:fs";
import * as net from "node:net";

import { ValidationError } from "./errors.js";
import { isHumanMode, isSocketRequested } from "./mode.js";
import { VERSION } from "./version.js";

const MAX_RETRIES = 3;
// Cap each answer line at 1 MiB; exceeding it consumes a retry (R10).
const MAX_LINE_BYTES = 1_048_576;
// sun_path limit for AF_UNIX paths.
const MAX_SOCKET_PATH_BYTES = 104;

// Unique sentinel emitted when a single line exceeds the byte cap. A distinct
// object (compared by identity) so it can never collide with client input.
const OVERFLOW: unique symbol = Symbol("line-overflow");
type ReadResult = string | typeof OVERFLOW | null;

/**
 * A client connection with manual byte buffering. Raw bytes are split on "\n";
 * complete lines are queued and a residual partial line is retained so that
 * batched input (multiple lines, or a line split across packets) is handled
 * correctly (R10 / ts-socket-1).
 */
class Connection {
  readonly socket: net.Socket;
  private _lines: ReadResult[] = [];
  private _residual = "";
  private _residualBytes = 0;
  private _overflow = false;
  private _closed = false;
  private _waiter: ((line: ReadResult) => void) | null = null;

  constructor(socket: net.Socket) {
    this.socket = socket;
    socket.on("data", (chunk: Buffer) => this._onData(chunk));
    socket.on("close", () => this._onEnd());
    socket.on("end", () => this._onEnd());
    socket.on("error", () => this._onEnd());
  }

  private _onData(chunk: Buffer): void {
    let start = 0;
    for (let i = 0; i < chunk.length; i++) {
      if (chunk[i] === 0x0a /* \n */) {
        const segment = chunk.toString("utf8", start, i);
        start = i + 1;
        if (this._overflow) {
          // The line that overflowed ends here: emit a sentinel overflow line.
          this._residual = "";
          this._residualBytes = 0;
          this._overflow = false;
          this._emit(OVERFLOW);
        } else {
          this._emit(this._residual + segment);
          this._residual = "";
          this._residualBytes = 0;
        }
      }
    }
    if (start < chunk.length) {
      this._residualBytes += chunk.length - start;
      if (this._residualBytes > MAX_LINE_BYTES) {
        // Drop the partial; mark overflow so the eventual newline yields a cap error.
        this._overflow = true;
        this._residual = "";
      } else if (!this._overflow) {
        this._residual += chunk.toString("utf8", start);
      }
    }
  }

  private _emit(line: ReadResult): void {
    if (this._waiter) {
      const w = this._waiter;
      this._waiter = null;
      w(line);
    } else {
      this._lines.push(line);
    }
  }

  private _onEnd(): void {
    if (this._closed) return;
    this._closed = true;
    if (this._waiter) {
      const w = this._waiter;
      this._waiter = null;
      w(null);
    }
  }

  /** Return the next buffered line, or wait for one. null on close/EOF. */
  readLine(): Promise<ReadResult> {
    if (this._lines.length > 0) return Promise.resolve(this._lines.shift() as ReadResult);
    if (this._closed) return Promise.resolve(null);
    return new Promise((resolve) => {
      this._waiter = resolve;
    });
  }

  close(): void {
    try {
      this.socket.destroy();
    } catch {
      // ignore
    }
  }
}

export class SocketTransport {
  readonly path: string;
  private _server: net.Server;
  private _stdoutHandshakeSent = false;
  private _socketHandshakeSent = false;
  private _step = 0;
  // FIFO queue of connections that have arrived but are not yet consumed, plus
  // a single waiter registered while a cycle is blocked on _accept (ts-socket-2).
  private _pendingConns: Connection[] = [];
  private _acceptWaiter: ((conn: Connection) => void) | null = null;
  private _cleanedUp = false;
  private _onSigint: () => void;
  private _onSigterm: () => void;
  private _onExit: () => void;

  constructor(path?: string) {
    this.path = path ?? `/tmp/inquirer-ai-${process.pid}.sock`;
    if (path !== undefined) {
      validateSocketPath(path);
    }

    // Stale-socket cleanup: lstat WITHOUT following symlinks. If a socket file
    // exists, unlink it; if a non-socket exists, refuse to start (R10).
    prepareSocketPath(this.path);

    this._server = net.createServer();
    this._server.on("error", (err: Error) => {
      // Surface listen errors as a clear failure rather than an unhandled event.
      throw err;
    });
    this._server.listen(this.path, () => {
      // Tighten permissions once the socket file exists (R10).
      try {
        fs.chmodSync(this.path, 0o600);
      } catch {
        // ignore — best effort
      }
    });
    // Don't keep event loop alive when not actively waiting for a connection.
    this._server.unref();

    this._server.on("connection", (socket: net.Socket) => {
      const conn = new Connection(socket);
      if (this._acceptWaiter) {
        const resolve = this._acceptWaiter;
        this._acceptWaiter = null;
        this._server.unref();
        resolve(conn);
      } else {
        // No one waiting yet: queue it so it isn't dropped/leaked (ts-socket-2).
        this._pendingConns.push(conn);
      }
    });

    this._sendStdoutHandshake();

    // Remove the socket file on SIGINT, SIGTERM, and normal exit (R10).
    this._onExit = () => this.cleanup();
    this._onSigterm = () => {
      this.cleanup();
      process.exit(0);
    };
    this._onSigint = () => {
      this.cleanup();
      process.exit(130);
    };
    process.on("exit", this._onExit);
    process.on("SIGTERM", this._onSigterm);
    process.on("SIGINT", this._onSigint);
  }

  cleanup(): void {
    if (this._cleanedUp) return;
    this._cleanedUp = true;
    process.removeListener("exit", this._onExit);
    process.removeListener("SIGTERM", this._onSigterm);
    process.removeListener("SIGINT", this._onSigint);
    try {
      this._server.close();
    } catch {
      // ignore
    }
    for (const conn of this._pendingConns) conn.close();
    this._pendingConns = [];
    try {
      fs.unlinkSync(this.path);
    } catch {
      // ignore
    }
  }

  private _handshakePayload(): Record<string, unknown> {
    return {
      kind: "handshake",
      protocol: "inquirer-ai",
      version: VERSION,
      format: "jsonl",
      socket: this.path,
      interaction: "sequential",
      total: null,
      description:
        "Interactive prompt protocol over Unix socket. " +
        "Connect to read a prompt, send a JSON answer, receive status. " +
        "One connection per prompt.",
      example_response: { answer: "<value>" },
    };
  }

  private _sendStdoutHandshake(): void {
    if (this._stdoutHandshakeSent) return;
    const payload = this._handshakePayload();
    process.stdout.write(`${JSON.stringify(payload)}\n`);
    // Set the flag only after the write succeeds (R10).
    this._stdoutHandshakeSent = true;
  }

  private _accept(): Promise<Connection> {
    const queued = this._pendingConns.shift();
    if (queued) return Promise.resolve(queued);
    // Keep event loop alive while waiting for a connection.
    this._server.ref();
    return new Promise((resolve) => {
      this._acceptWaiter = (conn: Connection) => resolve(conn);
    });
  }

  private _writeTo(socket: net.Socket, data: Record<string, unknown>): void {
    try {
      socket.write(`${JSON.stringify(data)}\n`);
    } catch {
      // ignore — peer may have gone away
    }
  }

  /**
   * Write a final frame and half-close the socket. Using end(data) (instead of
   * an immediate destroy) flushes the payload so error/validation/accepted
   * frames are not truncated (ts-socket-4).
   */
  private _endWith(conn: Connection, data: Record<string, unknown>): void {
    try {
      conn.socket.end(`${JSON.stringify(data)}\n`);
    } catch {
      // ignore — peer may have gone away (e.g. BrokenPipe)
    }
  }

  async promptCycle<T>(
    payload: Record<string, unknown>,
    validateFn: (value: unknown) => T,
    filterFn?: ((value: T) => T) | null,
    userValidate?: ((value: T) => string | boolean | null | undefined) | null,
  ): Promise<T> {
    this._step++;
    // Copy before injecting step so the caller's payload is not mutated.
    const promptPayload = { ...payload, step: this._step };
    let retriesUsed = 0;

    while (retriesUsed < MAX_RETRIES) {
      const conn = await this._accept();

      try {
        // Send handshake on first socket connection; set flag only after write.
        if (!this._socketHandshakeSent) {
          this._writeTo(conn.socket, this._handshakePayload());
          this._socketHandshakeSent = true;
        }

        // Send prompt
        this._writeTo(conn.socket, promptPayload);

        while (retriesUsed < MAX_RETRIES) {
          let line = await conn.readLine();
          if (line === null) {
            // Client disconnected without answering - re-queue on a new conn.
            break;
          }

          // Skip a leading handshake_ack and any blank keep-alive lines.
          let parsed: Record<string, unknown> | null = null;
          let consumed = false;
          while (line !== null) {
            // A line that exceeded the byte cap consumes a retry (R10).
            if (line === OVERFLOW) {
              retriesUsed++;
              const msg = `Answer exceeds maximum size of ${MAX_LINE_BYTES} bytes`;
              if (retriesUsed >= MAX_RETRIES) {
                this._endWith(conn, { kind: "error", message: msg });
                throw new ValidationError(msg);
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: msg });
              line = await conn.readLine();
              continue;
            }
            const trimmed = line.trim();
            if (trimmed === "") {
              line = await conn.readLine();
              continue;
            }
            // Parsing untrusted JSON must never crash (R10).
            try {
              const raw: unknown = JSON.parse(trimmed);
              if (typeof raw !== "object" || raw === null) {
                throw new SyntaxError("not an object");
              }
              parsed = raw as Record<string, unknown>;
            } catch (err) {
              retriesUsed++;
              const detail = err instanceof Error ? err.message : String(err);
              const msg = `Invalid JSON response: ${detail}`;
              if (retriesUsed >= MAX_RETRIES) {
                this._endWith(conn, { kind: "error", message: msg });
                throw new ValidationError(msg);
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: msg });
              line = await conn.readLine();
              continue;
            }
            if (parsed.kind === "handshake_ack") {
              parsed = null;
              line = await conn.readLine();
              continue;
            }
            consumed = true;
            break;
          }

          if (line === null) break; // client disconnected mid-handshake
          if (!consumed || parsed === null) continue;

          // Must be an object with an "answer" field (R7).
          if (!("answer" in parsed)) {
            retriesUsed++;
            const msg = 'Answer must be a JSON object with an "answer" field';
            if (retriesUsed >= MAX_RETRIES) {
              this._endWith(conn, { kind: "error", message: msg });
              throw new ValidationError(msg);
            }
            this._writeTo(conn.socket, { kind: "validation_error", message: msg });
            continue;
          }

          const answer: unknown = parsed.answer;

          // Type-coercion validation through the prompt's validateAnswer.
          let result: T;
          try {
            result = validateFn(answer);
          } catch (err) {
            if (err instanceof ValidationError) {
              retriesUsed++;
              if (retriesUsed >= MAX_RETRIES) {
                this._endWith(conn, { kind: "error", message: err.message });
                throw err;
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: err.message });
              continue;
            }
            // A non-ValidationError is fatal: report it and exit (R10).
            const msg = err instanceof Error ? err.message : String(err);
            this._endWith(conn, { kind: "error", message: msg });
            throw err;
          }

          // User validation runs on the coerced value BEFORE filter (R11).
          if (userValidate) {
            let error: string | null = null;
            let fatal: unknown = null;
            try {
              const validationResult = userValidate(result);
              if (typeof validationResult === "string") {
                error = validationResult;
              } else if (validationResult === false) {
                error = "Validation failed";
              }
              // true, null, undefined = valid
            } catch (err) {
              if (err instanceof ValidationError) {
                error = err.message;
              } else {
                // A non-ValidationError from user validate() is fatal (R10).
                fatal = err;
                error = err instanceof Error ? err.message : String(err);
              }
            }

            if (fatal) {
              this._endWith(conn, { kind: "error", message: error ?? String(fatal) });
              throw fatal;
            }

            if (error) {
              retriesUsed++;
              if (retriesUsed >= MAX_RETRIES) {
                this._endWith(conn, { kind: "error", message: error });
                throw new ValidationError(error);
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: error });
              continue;
            }
          }

          // All valid — apply filter only once on the accepted value, compute
          // the result, then write "accepted". Do not lose the answer if the
          // write fails (e.g. BrokenPipe): _endWith suppresses errors (R10).
          if (filterFn) {
            result = filterFn(result);
          }
          this._endWith(conn, { status: "accepted" });
          return result;
        }
      } catch (err) {
        // Every throw reaching here is intentional and fatal: a budget-exhausted
        // ValidationError, or a non-ValidationError from validateAnswer/validate
        // (already reported as {"kind":"error"}). Connection read failures
        // surface as a null line and `break` (not a throw), so they re-queue
        // without entering this catch. Propagate so the answer is never lost.
        throw err;
      } finally {
        conn.close();
      }
    }

    throw new ValidationError("Maximum validation retries exceeded");
  }
}

/**
 * Prepare the socket path before bind. lstat WITHOUT following symlinks: if a
 * socket already exists, unlink it (stale cleanup); if a non-socket exists,
 * refuse to start; permission/dir errors become clean handled errors (R10).
 */
function prepareSocketPath(p: string): void {
  let st: fs.Stats;
  try {
    st = fs.lstatSync(p);
  } catch {
    // Does not exist (or unreadable) — nothing to clean up.
    return;
  }
  if (st.isSocket()) {
    try {
      fs.unlinkSync(p);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Cannot remove stale socket at ${p}: ${msg}`);
    }
    return;
  }
  throw new Error(`Refusing to bind: ${p} exists and is not a socket`);
}

/**
 * Validate an explicit INQUIRER_AI_SOCKET path: must be a non-empty ABSOLUTE
 * path, length < 104 bytes, with an existing parent directory (R10).
 */
function validateSocketPath(p: string): void {
  if (p === "") {
    throw new Error("INQUIRER_AI_SOCKET must be a non-empty path");
  }
  if (!p.startsWith("/")) {
    throw new Error(`INQUIRER_AI_SOCKET must be an absolute path: ${p}`);
  }
  if (Buffer.byteLength(p, "utf8") >= MAX_SOCKET_PATH_BYTES) {
    throw new Error(
      `INQUIRER_AI_SOCKET path is too long (must be < ${MAX_SOCKET_PATH_BYTES} bytes): ${p}`,
    );
  }
  const dir = p.slice(0, p.lastIndexOf("/")) || "/";
  let dirStat: fs.Stats;
  try {
    dirStat = fs.statSync(dir);
  } catch {
    throw new Error(`INQUIRER_AI_SOCKET parent directory does not exist: ${dir}`);
  }
  if (!dirStat.isDirectory()) {
    throw new Error(`INQUIRER_AI_SOCKET parent is not a directory: ${dir}`);
  }
}

// Module-level singleton with lazy initialization
let _transport: SocketTransport | null = null;
let _transportChecked = false;

export function getSocketTransport(): SocketTransport | null {
  if (_transport !== null) return _transport;
  if (_transportChecked) return null;
  _transportChecked = true;

  // Transport selection (R3): use the SOCKET transport iff a socket is
  // requested AND NOT INQUIRER_AI_TRANSPORT == "stdio" AND unix sockets are
  // available; otherwise fall back to the stdio agent transport.
  if (isHumanMode()) return null;
  if (process.platform === "win32") return null;
  if ((process.env.INQUIRER_AI_TRANSPORT ?? "").toLowerCase() === "stdio") return null;
  if (!isSocketRequested()) return null;

  // INQUIRER_AI_SOCKET (if set & non-empty) selects the socket path; otherwise
  // a per-pid default path is used.
  const socketPath = process.env.INQUIRER_AI_SOCKET;
  _transport = socketPath ? new SocketTransport(socketPath) : new SocketTransport();
  return _transport;
}

export function resetSocketTransport(): void {
  if (_transport !== null) {
    _transport.cleanup();
    _transport = null;
  }
  _transportChecked = false;
}
