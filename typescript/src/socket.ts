import * as fs from "node:fs";
import * as net from "node:net";
import * as readline from "node:readline";

import { ValidationError } from "./errors.js";
import { isAgentMode } from "./mode.js";

const VERSION = "0.2.1";
const MAX_RETRIES = 3;

interface Connection {
  socket: net.Socket;
  rline: readline.Interface;
}

export class SocketTransport {
  readonly path: string;
  private _server: net.Server;
  private _stdoutHandshakeSent = false;
  private _socketHandshakeSent = false;
  private _step = 0;
  private _pendingAccept: ((conn: Connection) => void) | null = null;
  private _cleanedUp = false;

  constructor(path?: string) {
    this.path = path ?? `/tmp/inquirer-ai-${process.pid}.sock`;

    // Remove stale socket file if it exists
    try {
      fs.unlinkSync(this.path);
    } catch {
      // ignore
    }

    this._server = net.createServer();
    this._server.listen(this.path);
    // Don't keep event loop alive when not actively waiting for a connection
    this._server.unref();

    this._server.on("connection", (socket: net.Socket) => {
      const rline = readline.createInterface({ input: socket, terminal: false });
      const conn: Connection = { socket, rline };
      if (this._pendingAccept) {
        const resolve = this._pendingAccept;
        this._pendingAccept = null;
        resolve(conn);
      }
    });

    this._sendStdoutHandshake();

    // Cleanup handlers
    process.on("exit", () => this.cleanup());
    process.on("SIGTERM", () => {
      this.cleanup();
      process.exit(0);
    });
  }

  cleanup(): void {
    if (this._cleanedUp) return;
    this._cleanedUp = true;
    try {
      this._server.close();
    } catch {
      // ignore
    }
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
    this._stdoutHandshakeSent = true;
    const payload = this._handshakePayload();
    process.stdout.write(`${JSON.stringify(payload)}\n`);
  }

  private _accept(): Promise<Connection> {
    // Keep event loop alive while waiting for a connection
    this._server.ref();
    return new Promise((resolve) => {
      this._pendingAccept = (conn: Connection) => {
        // Allow event loop to exit when not waiting
        this._server.unref();
        resolve(conn);
      };
    });
  }

  private _writeTo(socket: net.Socket, data: Record<string, unknown>): void {
    socket.write(`${JSON.stringify(data)}\n`);
  }

  private _readLine(conn: Connection): Promise<string | null> {
    return new Promise((resolve) => {
      const { socket, rline } = conn;

      let resolved = false;

      const onLine = (line: string) => {
        if (resolved) return;
        resolved = true;
        cleanup();
        resolve(line);
      };

      const onClose = () => {
        if (resolved) return;
        resolved = true;
        cleanup();
        resolve(null);
      };

      const onError = () => {
        if (resolved) return;
        resolved = true;
        cleanup();
        resolve(null);
      };

      const cleanup = () => {
        rline.removeListener("line", onLine);
        rline.removeListener("close", onClose);
        socket.removeListener("close", onClose);
        socket.removeListener("error", onError);
      };

      rline.on("line", onLine);
      rline.on("close", onClose);
      socket.on("close", onClose);
      socket.on("error", onError);
    });
  }

  private _closeConnection(conn: Connection): void {
    try {
      conn.rline.close();
    } catch {
      // ignore
    }
    try {
      conn.socket.destroy();
    } catch {
      // ignore
    }
  }

  async promptCycle<T>(
    payload: Record<string, unknown>,
    validateFn: (value: unknown) => T,
    filterFn?: ((value: T) => T) | null,
    userValidate?: ((value: T) => string | boolean | null | undefined) | null,
  ): Promise<T> {
    this._step++;
    const promptPayload = { ...payload, step: this._step };
    let retriesUsed = 0;

    while (retriesUsed < MAX_RETRIES) {
      const conn = await this._accept();

      try {
        // Send handshake on first socket connection
        if (!this._socketHandshakeSent) {
          this._writeTo(conn.socket, this._handshakePayload());
          this._socketHandshakeSent = true;
        }

        // Send prompt
        this._writeTo(conn.socket, promptPayload);

        while (retriesUsed < MAX_RETRIES) {
          const line = await this._readLine(conn);
          if (line === null || line.trim() === "") {
            // Client disconnected without answering - re-queue
            break;
          }

          const trimmed = line.trim();

          // Parse JSON
          let parsed: Record<string, unknown>;
          try {
            const raw: unknown = JSON.parse(trimmed);
            if (typeof raw !== "object" || raw === null) {
              throw new SyntaxError("not an object");
            }
            parsed = raw as Record<string, unknown>;
          } catch {
            retriesUsed++;
            const msg = `Invalid JSON: ${trimmed}`;
            if (retriesUsed >= MAX_RETRIES) {
              this._writeTo(conn.socket, { kind: "error", message: msg });
              this._closeConnection(conn);
              throw new ValidationError(msg);
            }
            this._writeTo(conn.socket, { kind: "validation_error", message: msg });
            continue;
          }

          // Handle handshake_ack - skip it and read next line
          if (typeof parsed === "object" && parsed !== null && parsed.kind === "handshake_ack") {
            const nextLine = await this._readLine(conn);
            if (nextLine === null || nextLine.trim() === "") {
              break;
            }
            try {
              const rawNext: unknown = JSON.parse(nextLine.trim());
              if (typeof rawNext !== "object" || rawNext === null) {
                throw new SyntaxError("not an object");
              }
              parsed = rawNext as Record<string, unknown>;
            } catch {
              retriesUsed++;
              const msg = `Invalid JSON: ${nextLine.trim()}`;
              if (retriesUsed >= MAX_RETRIES) {
                this._writeTo(conn.socket, { kind: "error", message: msg });
                this._closeConnection(conn);
                throw new ValidationError(msg);
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: msg });
              continue;
            }
          }

          // Must have "answer" key
          if (typeof parsed !== "object" || parsed === null || !("answer" in parsed)) {
            retriesUsed++;
            const msg = 'Response must be a JSON object with an "answer" key';
            if (retriesUsed >= MAX_RETRIES) {
              this._writeTo(conn.socket, { kind: "error", message: msg });
              this._closeConnection(conn);
              throw new ValidationError(msg);
            }
            this._writeTo(conn.socket, { kind: "validation_error", message: msg });
            continue;
          }

          const answer: unknown = parsed.answer;

          // Validate through prompt's validateAnswer
          let result: T;
          try {
            result = validateFn(answer);
          } catch (err) {
            if (err instanceof ValidationError) {
              retriesUsed++;
              if (retriesUsed >= MAX_RETRIES) {
                this._writeTo(conn.socket, { kind: "error", message: err.message });
                this._closeConnection(conn);
                throw err;
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: err.message });
              continue;
            }
            throw err;
          }

          // Apply filter
          if (filterFn) {
            result = filterFn(result);
          }

          // Run user validation
          if (userValidate) {
            let error: string | null = null;
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
                error = err instanceof Error ? err.message : String(err);
              }
            }

            if (error) {
              retriesUsed++;
              if (retriesUsed >= MAX_RETRIES) {
                this._writeTo(conn.socket, { kind: "error", message: error });
                this._closeConnection(conn);
                throw new ValidationError(error);
              }
              this._writeTo(conn.socket, { kind: "validation_error", message: error });
              continue;
            }
          }

          // All valid
          this._writeTo(conn.socket, { status: "accepted" });
          this._closeConnection(conn);
          return result;
        }
      } catch (err) {
        if (err instanceof ValidationError) throw err;
        // Connection error - re-queue
      } finally {
        this._closeConnection(conn);
      }
    }

    throw new ValidationError("Maximum validation retries exceeded");
  }
}

// Module-level singleton with lazy initialization
let _transport: SocketTransport | null = null;
let _transportChecked = false;

export function getSocketTransport(): SocketTransport | null {
  if (_transport !== null) return _transport;
  if (_transportChecked) return null;
  _transportChecked = true;

  const envMode = (process.env.INQUIRER_AI_MODE ?? "").toLowerCase();
  if (envMode === "human") return null;
  if (process.platform === "win32") return null;
  if ((process.env.INQUIRER_AI_TRANSPORT ?? "").toLowerCase() === "stdio") return null;

  const socketPath = process.env.INQUIRER_AI_SOCKET;
  if (socketPath) {
    _transport = new SocketTransport(socketPath);
    return _transport;
  }

  if (isAgentMode()) {
    _transport = new SocketTransport();
    return _transport;
  }

  return null;
}

export function resetSocketTransport(): void {
  if (_transport !== null) {
    _transport.cleanup();
    _transport = null;
  }
  _transportChecked = false;
}
