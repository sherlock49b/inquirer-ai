import { type ChildProcess, spawn } from "node:child_process";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import * as readline from "node:readline";
import { afterEach, describe, expect, it } from "vitest";

const NODE = process.execPath;
const DIST = path.resolve(__dirname, "../dist");

// --- Helper: temp directory for each test ---
function tmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "inquirer-ai-sock-"));
}

// --- Helper: wait for socket file ---
function waitForSocket(sockPath: string, timeout = 5000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;
    const check = () => {
      if (fs.existsSync(sockPath)) {
        resolve();
      } else if (Date.now() > deadline) {
        reject(new Error(`Socket ${sockPath} not created within ${timeout}ms`));
      } else {
        setTimeout(check, 50);
      }
    };
    check();
  });
}

// --- Helper: connect to socket ---
function connectSocket(sockPath: string): Promise<net.Socket> {
  return new Promise((resolve, reject) => {
    const sock = net.createConnection(sockPath, () => resolve(sock));
    sock.on("error", reject);
    sock.setTimeout(5000);
  });
}

// --- Helper: read lines until we get a prompt ---
interface ParsedMessage {
  kind?: string;
  [key: string]: unknown;
}

function readUntilPrompt(sock: net.Socket): Promise<ParsedMessage[]> {
  return new Promise((resolve, reject) => {
    const messages: ParsedMessage[] = [];
    const rl = readline.createInterface({ input: sock, terminal: false });
    const timeout = setTimeout(() => {
      rl.close();
      reject(new Error("Timeout waiting for prompt"));
    }, 5000);

    rl.on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      try {
        const parsed = JSON.parse(trimmed) as ParsedMessage;
        messages.push(parsed);
        if (parsed.kind === "prompt") {
          clearTimeout(timeout);
          rl.close();
          resolve(messages);
        }
      } catch {
        clearTimeout(timeout);
        rl.close();
        reject(new Error(`Invalid JSON: ${trimmed}`));
      }
    });
    rl.on("close", () => {
      clearTimeout(timeout);
      if (messages.length === 0) {
        reject(new Error("Connection closed before prompt received"));
      } else {
        resolve(messages);
      }
    });
    sock.on("error", (err) => {
      clearTimeout(timeout);
      rl.close();
      reject(err);
    });
  });
}

// --- Helper: send answer and read response ---
function sendAnswer(sock: net.Socket, answer: unknown): Promise<ParsedMessage> {
  return new Promise((resolve, reject) => {
    const rl = readline.createInterface({ input: sock, terminal: false });
    const timeout = setTimeout(() => {
      rl.close();
      reject(new Error("Timeout waiting for answer response"));
    }, 5000);

    rl.on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      clearTimeout(timeout);
      rl.close();
      try {
        resolve(JSON.parse(trimmed) as ParsedMessage);
      } catch {
        reject(new Error(`Invalid JSON response: ${trimmed}`));
      }
    });
    rl.on("close", () => {
      clearTimeout(timeout);
    });
    sock.on("error", (err) => {
      clearTimeout(timeout);
      rl.close();
      reject(err);
    });

    sock.write(`${JSON.stringify({ answer })}\n`);
  });
}

// --- Helper: read stdout handshake ---
function readStdoutHandshake(proc: ChildProcess, timeout = 5000): Promise<ParsedMessage> {
  return new Promise((resolve, reject) => {
    if (!proc.stdout) return reject(new Error("No stdout"));
    const rl = readline.createInterface({ input: proc.stdout, terminal: false });
    const timer = setTimeout(() => {
      rl.close();
      reject(new Error("Timeout waiting for stdout handshake"));
    }, timeout);

    rl.on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      clearTimeout(timer);
      rl.close();
      try {
        resolve(JSON.parse(trimmed) as ParsedMessage);
      } catch {
        reject(new Error(`Invalid JSON on stdout: ${trimmed}`));
      }
    });
  });
}

// --- Helper: run a test script ---
function runScript(script: string, sockPath: string): ChildProcess {
  const env: Record<string, string> = {
    ...process.env as Record<string, string>,
    INQUIRER_AI_SOCKET: sockPath,
  };
  delete env.INQUIRER_AI_MODE;

  return spawn(NODE, ["--input-type=module", "-e", script], {
    env,
    stdio: ["pipe", "pipe", "pipe"],
  });
}

// --- Helper: wait for process and get stderr ---
function waitForProc(proc: ChildProcess, timeout = 5000): Promise<string> {
  return new Promise((resolve, reject) => {
    let stderr = "";
    if (proc.stderr) {
      proc.stderr.on("data", (chunk: Buffer) => {
        stderr += chunk.toString();
      });
    }
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      reject(new Error(`Process did not exit within ${timeout}ms. stderr: ${stderr}`));
    }, timeout);

    proc.on("exit", () => {
      clearTimeout(timer);
      resolve(stderr);
    });
  });
}

// --- Test scripts ---
const SCRIPT_TEXT = `
import { text } from "${DIST}/index.js";
const name = await text({ message: "Name?" });
process.stderr.write("RESULT:" + name + "\\n");
`;

const SCRIPT_SELECT = `
import { SelectPrompt } from "${DIST}/prompts/select.js";
const lang = await new SelectPrompt({
  message: "Language?",
  choices: ["Python", "Go", "Rust"],
}).execute();
process.stderr.write("RESULT:" + lang + "\\n");
`;

const SCRIPT_NUMBER = `
import { NumberPrompt } from "${DIST}/prompts/number.js";
const port = await new NumberPrompt({
  message: "Port?",
  min: 1024,
  max: 65535,
}).execute();
process.stderr.write("RESULT:" + port + "\\n");
`;

const SCRIPT_MULTI = `
import { text, confirm } from "${DIST}/index.js";
const name = await text({ message: "Name?" });
const ok = await confirm({ message: "Sure?", default: true });
process.stderr.write("RESULT:" + name + "," + ok + "\\n");
`;

const SCRIPT_VALIDATE = `
import { text } from "${DIST}/index.js";
const email = await text({
  message: "Email?",
  validate: (v) => v.includes("@") || "must contain @",
});
process.stderr.write("RESULT:" + email + "\\n");
`;

const SCRIPT_VALIDATE_THROWS = `
import { text } from "${DIST}/index.js";
const v = await text({
  message: "X?",
  validate: () => { throw new Error("boom-non-validation"); },
});
process.stderr.write("RESULT:" + v + "\\n");
`;

const SCRIPT_SEARCH_ASYNC = `
import { search } from "${DIST}/index.js";
const pkg = await search({
  message: "Package?",
  source: async () => {
    await new Promise((r) => setTimeout(r, 10));
    return [
      { name: "requests", value: "requests" },
      { name: "httpx", value: "httpx" },
    ];
  },
});
process.stderr.write("RESULT:" + pkg + "\\n");
`;

// Track processes for cleanup
const procs: ChildProcess[] = [];

afterEach(() => {
  for (const p of procs) {
    try {
      p.kill("SIGKILL");
    } catch {
      // ignore
    }
  }
  procs.length = 0;
});

describe("Socket transport", () => {
  it("basic text prompt", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    const msgs = await readUntilPrompt(sock);
    expect(msgs[0]!.kind).toBe("handshake");
    expect(msgs[0]!.protocol).toBe("inquirer-ai");
    expect(msgs[0]!.socket).toBe(sockPath);
    expect(msgs[1]!.kind).toBe("prompt");
    expect(msgs[1]!.type).toBe("input");
    expect(msgs[1]!.message).toBe("Name?");

    const resp = await sendAnswer(sock, "Alice");
    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:Alice");
  });

  it("select prompt", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_SELECT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    const msgs = await readUntilPrompt(sock);
    const prompt = msgs[msgs.length - 1]!;
    expect(prompt.type).toBe("select");
    expect(prompt.choices).toHaveLength(3);

    const resp = await sendAnswer(sock, "Go");
    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:Go");
  });

  it("peek then answer", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    // First connection: peek (read prompt, don't answer)
    const sock1 = await connectSocket(sockPath);
    const msgs1 = await readUntilPrompt(sock1);
    expect(msgs1[msgs1.length - 1]!.kind).toBe("prompt");
    sock1.destroy();
    await new Promise((r) => setTimeout(r, 100));

    // Second connection: same prompt, now answer
    const sock2 = await connectSocket(sockPath);
    const msgs2 = await readUntilPrompt(sock2);
    expect(msgs2[0]!.kind).toBe("prompt");
    expect(msgs2[0]!.message).toBe("Name?");

    const resp = await sendAnswer(sock2, "Bob");
    expect(resp.status).toBe("accepted");
    sock2.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:Bob");
  });

  it("validation retry on same connection", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_NUMBER, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Send invalid value (below min)
    const resp1 = await sendAnswer(sock, 80);
    expect(resp1.kind).toBe("validation_error");
    expect(resp1.message as string).toContain("1024");

    // Send valid value
    const resp2 = await sendAnswer(sock, 8080);
    expect(resp2.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:8080");
  });

  it("user validation retry", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_VALIDATE, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Invalid - no @ sign
    const resp1 = await sendAnswer(sock, "invalid");
    expect(resp1.kind).toBe("validation_error");
    expect(resp1.message as string).toContain("@");

    // Valid
    const resp2 = await sendAnswer(sock, "test@example.com");
    expect(resp2.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:test@example.com");
  });

  it("multi-prompt sequence", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_MULTI, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    // First prompt
    const sock1 = await connectSocket(sockPath);
    const msgs1 = await readUntilPrompt(sock1);
    expect(msgs1[msgs1.length - 1]!.type).toBe("input");
    expect(msgs1[msgs1.length - 1]!.step).toBe(1);
    const resp1 = await sendAnswer(sock1, "Charlie");
    expect(resp1.status).toBe("accepted");
    sock1.destroy();

    // Second prompt
    const sock2 = await connectSocket(sockPath);
    const msgs2 = await readUntilPrompt(sock2);
    expect(msgs2[0]!.type).toBe("confirm");
    expect(msgs2[0]!.step).toBe(2);
    const resp2 = await sendAnswer(sock2, false);
    expect(resp2.status).toBe("accepted");
    sock2.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:Charlie,false");
  });

  it("handshake on stdout with socket path", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const handshake = await readStdoutHandshake(proc);
    expect(handshake.kind).toBe("handshake");
    expect(handshake.protocol).toBe("inquirer-ai");
    expect(handshake.socket).toBe(sockPath);

    // Finish the prompt so process exits
    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);
    await sendAnswer(sock, "done");
    sock.destroy();

    await waitForProc(proc);
  });

  it("handshake only on first socket connection", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_MULTI, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    // First connection: handshake + prompt
    const sock1 = await connectSocket(sockPath);
    const msgs1 = await readUntilPrompt(sock1);
    expect(msgs1).toHaveLength(2);
    expect(msgs1[0]!.kind).toBe("handshake");
    expect(msgs1[1]!.kind).toBe("prompt");
    await sendAnswer(sock1, "test");
    sock1.destroy();

    // Second connection: prompt only (no handshake)
    const sock2 = await connectSocket(sockPath);
    const msgs2 = await readUntilPrompt(sock2);
    expect(msgs2).toHaveLength(1);
    expect(msgs2[0]!.kind).toBe("prompt");
    await sendAnswer(sock2, true);
    sock2.destroy();

    await waitForProc(proc);
  });

  it("socket cleanup on exit", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);
    expect(fs.existsSync(sockPath)).toBe(true);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);
    await sendAnswer(sock, "done");
    sock.destroy();

    await waitForProc(proc);
    // Give a brief moment for cleanup
    await new Promise((r) => setTimeout(r, 200));
    expect(fs.existsSync(sockPath)).toBe(false);
  });

  it("rapid reconnection", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    // Peek: connect, read prompt, disconnect immediately
    const sock1 = await connectSocket(sockPath);
    const msgs1 = await readUntilPrompt(sock1);
    expect(msgs1[msgs1.length - 1]!.step).toBe(1);
    sock1.destroy();

    // Immediately reconnect — no delay. The re-sent prompt is the SAME logical
    // prompt, so it must keep the same step (FIX A: re-sends reuse the step).
    const sock2 = await connectSocket(sockPath);
    const msgs = await readUntilPrompt(sock2);
    expect(msgs[0]!.kind).toBe("prompt");
    expect(msgs[0]!.message).toBe("Name?");
    expect(msgs[0]!.step).toBe(1);

    const resp = await sendAnswer(sock2, "rapid");
    expect(resp.status).toBe("accepted");
    sock2.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:rapid");
  });

  it("partial message - no newline then complete", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Send partial JSON without newline
    sock.write('{"answer": "part');

    // Small delay then complete the line
    await new Promise((r) => setTimeout(r, 100));
    sock.write('ial"}\n');

    // Read response
    const resp = await new Promise<ParsedMessage>((resolve, reject) => {
      const rl = readline.createInterface({ input: sock, terminal: false });
      const timeout = setTimeout(() => {
        rl.close();
        reject(new Error("Timeout waiting for response"));
      }, 5000);
      rl.on("line", (line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        clearTimeout(timeout);
        rl.close();
        resolve(JSON.parse(trimmed) as ParsedMessage);
      });
    });

    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:partial");
  });

  it("multiple clients - second after first disconnects", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    // Client 1: peek (read prompt, disconnect)
    const sock1 = await connectSocket(sockPath);
    const msgs1 = await readUntilPrompt(sock1);
    expect(msgs1[msgs1.length - 1]!.kind).toBe("prompt");
    sock1.destroy();
    await new Promise((r) => setTimeout(r, 100));

    // Client 2: answer
    const sock2 = await connectSocket(sockPath);
    const msgs2 = await readUntilPrompt(sock2);
    expect(msgs2[0]!.kind).toBe("prompt");
    expect(msgs2[0]!.message).toBe("Name?");

    const resp = await sendAnswer(sock2, "client2");
    expect(resp.status).toBe("accepted");
    sock2.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:client2");
  });

  it("socket cleanup on SIGTERM", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);
    expect(fs.existsSync(sockPath)).toBe(true);

    // Send SIGTERM instead of answering
    proc.kill("SIGTERM");

    await waitForProc(proc).catch(() => {
      // Process may exit with non-zero code from signal
    });
    await new Promise((r) => setTimeout(r, 200));
    expect(fs.existsSync(sockPath)).toBe(false);
  });

  it("large payload (100KB+)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Build a 100 KB+ string
    const largeValue = "x".repeat(100 * 1024);
    const resp = await sendAnswer(sock, largeValue);
    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc, 15000);
    expect(stderr).toContain("RESULT:");
    expect(stderr).toContain(largeValue.substring(0, 20));
  });

  it("auto socket in agent mode", async () => {
    const env: Record<string, string> = {
      ...process.env as Record<string, string>,
      INQUIRER_AI_MODE: "agent",
    };
    delete env.INQUIRER_AI_SOCKET;

    const script = `
import { text } from "${DIST}/index.js";
const name = await text({ message: "Name?" });
process.stderr.write("RESULT:" + name + "\\n");
`;

    const proc = spawn(NODE, ["--input-type=module", "-e", script], {
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });
    procs.push(proc);

    const handshake = await readStdoutHandshake(proc);
    expect(handshake.kind).toBe("handshake");
    expect(handshake.socket).toBeDefined();
    const sockPath = handshake.socket as string;
    expect(fs.existsSync(sockPath)).toBe(true);

    const sock = await connectSocket(sockPath);
    const msgs = await readUntilPrompt(sock);
    expect(msgs[msgs.length - 1]!.kind).toBe("prompt");
    const resp = await sendAnswer(sock, "auto-test");
    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:auto-test");
  });

  it("batched input: ack + answer sent in one write (ts-socket-1)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Write handshake_ack AND the answer as a single batched chunk. The
    // transport must buffer raw bytes, split on \n, and process both lines.
    const resp = await new Promise<ParsedMessage>((resolve, reject) => {
      const rl = readline.createInterface({ input: sock, terminal: false });
      const timeout = setTimeout(() => {
        rl.close();
        reject(new Error("Timeout"));
      }, 5000);
      rl.on("line", (line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        clearTimeout(timeout);
        rl.close();
        resolve(JSON.parse(trimmed) as ParsedMessage);
      });
      sock.write(`${JSON.stringify({ kind: "handshake_ack" })}\n${JSON.stringify({ answer: "batched" })}\n`);
    });

    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:batched");
  });

  it("invalid JSON yields validation_error then accepts (R7)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    // Send a non-JSON line; expect a validation_error with the canonical prefix.
    const resp1 = await new Promise<ParsedMessage>((resolve, reject) => {
      const rl = readline.createInterface({ input: sock, terminal: false });
      const timeout = setTimeout(() => { rl.close(); reject(new Error("Timeout")); }, 5000);
      rl.on("line", (line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        clearTimeout(timeout);
        rl.close();
        resolve(JSON.parse(trimmed) as ParsedMessage);
      });
      sock.write("not-json\n");
    });
    expect(resp1.kind).toBe("validation_error");
    expect(resp1.message as string).toContain("Invalid JSON response");

    const resp2 = await sendAnswer(sock, "recovered");
    expect(resp2.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:recovered");
  });

  it("async search source advertises resolved choices on the socket (R6)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_SEARCH_ASYNC, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    const msgs = await readUntilPrompt(sock);
    const prompt = msgs[msgs.length - 1]!;
    expect(prompt.type).toBe("search");
    expect(prompt.searchable).toBe(true);
    // The async source must be resolved and advertised, NOT an empty array.
    expect(prompt.choices).toEqual([
      { name: "requests", value: "requests" },
      { name: "httpx", value: "httpx" },
    ]);

    const resp = await sendAnswer(sock, "httpx");
    expect(resp.status).toBe("accepted");
    sock.destroy();

    const stderr = await waitForProc(proc);
    expect(stderr).toContain("RESULT:httpx");
  });

  it("refuses to bind when the socket path is a non-socket file (R10)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "regular-file");
    // Pre-create a regular file at the target path.
    fs.writeFileSync(sockPath, "i am not a socket");

    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    // The process must exit non-zero with a clear error and must NOT unlink
    // the non-socket file.
    let exitCode: number | null = null;
    let stderr = "";
    await new Promise<void>((resolve) => {
      if (proc.stderr) proc.stderr.on("data", (c: Buffer) => { stderr += c.toString(); });
      proc.on("exit", (code) => { exitCode = code; resolve(); });
    });
    expect(exitCode).not.toBe(0);
    expect(stderr.toLowerCase()).toContain("not a socket");
    // The pre-existing file must be untouched.
    expect(fs.existsSync(sockPath)).toBe(true);
    expect(fs.readFileSync(sockPath, "utf8")).toBe("i am not a socket");
  });

  it("rejects a relative INQUIRER_AI_SOCKET path (R10)", async () => {
    const proc = spawn(NODE, ["--input-type=module", "-e", SCRIPT_TEXT], {
      env: { ...(process.env as Record<string, string>), INQUIRER_AI_SOCKET: "relative.sock" },
      stdio: ["pipe", "pipe", "pipe"],
    });
    procs.push(proc);

    let exitCode: number | null = null;
    let stderr = "";
    await new Promise<void>((resolve) => {
      if (proc.stderr) proc.stderr.on("data", (c: Buffer) => { stderr += c.toString(); });
      proc.on("exit", (code) => { exitCode = code; resolve(); });
    });
    expect(exitCode).not.toBe(0);
    expect(stderr.toLowerCase()).toContain("absolute");
  });

  it("non-ValidationError from validate() -> {kind:error} and non-zero exit (R10)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_VALIDATE_THROWS, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);

    const sock = await connectSocket(sockPath);
    await readUntilPrompt(sock);

    const resp = await new Promise<ParsedMessage>((resolve, reject) => {
      const rl = readline.createInterface({ input: sock, terminal: false });
      const timeout = setTimeout(() => { rl.close(); reject(new Error("Timeout")); }, 5000);
      rl.on("line", (line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        clearTimeout(timeout);
        rl.close();
        resolve(JSON.parse(trimmed) as ParsedMessage);
      });
      sock.write(`${JSON.stringify({ answer: "anything" })}\n`);
    });
    // Reported as a fatal error frame, not a validation_error.
    expect(resp.kind).toBe("error");
    expect(resp.message as string).toContain("boom-non-validation");
    sock.destroy();

    let exitCode: number | null = null;
    await new Promise<void>((resolve) => {
      proc.on("exit", (code) => { exitCode = code; resolve(); });
    });
    expect(exitCode).not.toBe(0);
  });

  it("socket cleanup on SIGINT (ts-socket-3)", async () => {
    const dir = tmpDir();
    const sockPath = path.join(dir, "test.sock");
    const proc = runScript(SCRIPT_TEXT, sockPath);
    procs.push(proc);

    await waitForSocket(sockPath);
    expect(fs.existsSync(sockPath)).toBe(true);

    proc.kill("SIGINT");
    await waitForProc(proc).catch(() => {
      // Process exits from signal handling.
    });
    await new Promise((r) => setTimeout(r, 200));
    expect(fs.existsSync(sockPath)).toBe(false);
  });
}, 30000);
