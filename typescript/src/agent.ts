import * as readline from "node:readline";
import * as fs from "node:fs";

const VERSION = "0.2.0";

let handshakeSent = false;
let handshakeAck: Record<string, unknown> | null = null;
let rl: readline.Interface | null = null;
let lineBuffer: string[] = [];
let waiters: Array<(line: string | null) => void> = [];
let closed = false;
let agentStep = 0;

export function resetAgent(): void {
  handshakeSent = false;
  handshakeAck = null;
  agentStep = 0;
  outputStream = null;
  if (rl) {
    rl.removeAllListeners();
    rl.close();
    rl = null;
  }
  lineBuffer = [];
  waiters = [];
  closed = false;
}

function getOutputStream(): NodeJS.WritableStream {
  const fdOut = process.env["INQUIRER_AI_FD_OUT"];
  if (fdOut) {
    return fs.createWriteStream(null as unknown as string, {
      fd: parseInt(fdOut, 10),
    });
  }
  return process.stdout;
}

function getInputStream(): NodeJS.ReadableStream {
  const fdIn = process.env["INQUIRER_AI_FD_IN"];
  if (fdIn) {
    return fs.createReadStream(null as unknown as string, {
      fd: parseInt(fdIn, 10),
    });
  }
  return process.stdin;
}

let outputStream: NodeJS.WritableStream | null = null;

function getOutput(): NodeJS.WritableStream {
  if (!outputStream) {
    outputStream = getOutputStream();
  }
  return outputStream;
}

function ensureRL(): void {
  if (rl) return;
  closed = false;
  rl = readline.createInterface({
    input: getInputStream() as NodeJS.ReadableStream,
    terminal: false,
  });
  rl.on("line", (line: string) => {
    const waiter = waiters.shift();
    if (waiter) {
      waiter(line);
    } else {
      lineBuffer.push(line);
    }
  });
  rl.on("close", () => {
    closed = true;
    let waiter: ((v: string | null) => void) | undefined;
    while ((waiter = waiters.shift())) {
      waiter(null);
    }
  });
}

function writeLine(data: Record<string, unknown>): void {
  getOutput().write(JSON.stringify(data) + "\n");
}

function sendHandshake(): void {
  if (handshakeSent) return;
  handshakeSent = true;
  const meta = {
    kind: "handshake",
    protocol: "inquirer-ai",
    version: VERSION,
    format: "jsonl",
    interaction: "sequential",
    total: null,
    description:
      "Interactive prompt protocol. Prompts are sent one at a time — " +
      "read one JSON line from stdout, respond with one JSON line on stdin, " +
      "then wait for the next prompt. Do NOT send all answers at once. " +
      "Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication.",
    example_response: { answer: "<value>" },
  };
  writeLine(meta);
}

function readLine(): Promise<string | null> {
  ensureRL();
  const buffered = lineBuffer.shift();
  if (buffered !== undefined) return Promise.resolve(buffered);
  if (closed) return Promise.resolve(null);
  return new Promise((resolve) => {
    waiters.push(resolve);
  });
}

export async function agentSend(
  payload: Record<string, unknown>,
): Promise<void> {
  if (!handshakeSent) {
    sendHandshake();
  }
  agentStep++;
  writeLine({ kind: "prompt", step: agentStep, total: null, ...payload });
}

export function agentSendValidationError(message: string): void {
  writeLine({ kind: "validation_error", message });
}

export function agentSendError(message: string): void {
  writeLine({ kind: "error", message });
}

export function getHandshakeAck(): Record<string, unknown> | null {
  return handshakeAck;
}

export async function agentReceive(): Promise<unknown> {
  while (true) {
    const line = await readLine();
    if (line === null) {
      throw new Error(
        'No response received (stdin closed). Expected JSON like: {"answer": "<value>"}',
      );
    }
    let resp: Record<string, unknown>;
    try {
      resp = JSON.parse(line) as Record<string, unknown>;
    } catch {
      throw new Error(
        `Invalid JSON response: ${line.trim()}. Expected JSON like: {"answer": "<value>"}`,
      );
    }
    if (resp["kind"] === "handshake_ack") {
      handshakeAck = resp;
      continue;
    }
    if (typeof resp !== "object" || resp === null || !("answer" in resp)) {
      throw new Error(
        `Response must be a JSON object with an "answer" key, ` +
          `e.g. {"answer": "<value>"}. Got: ${line.trim()}`,
      );
    }
    return resp["answer"];
  }
}
