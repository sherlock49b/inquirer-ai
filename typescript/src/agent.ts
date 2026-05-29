import * as fs from "node:fs";
import * as readline from "node:readline";
import { VERSION } from "./version.js";

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
  outputFd = null;
  outputFdResolved = false;
  if (rl) {
    rl.removeAllListeners();
    rl.close();
    rl = null;
  }
  lineBuffer = [];
  waiters = [];
  closed = false;
}

// Resolve the configured output fd (INQUIRER_AI_FD_OUT) once. When set, output
// is written synchronously with fs.writeSync so data is flushed to the OS before
// the process can exit (R10); otherwise we fall back to process.stdout.
function getOutputFd(): number | null {
  const fdOut = process.env.INQUIRER_AI_FD_OUT;
  if (!fdOut) return null;
  const fd = parseInt(fdOut, 10);
  if (Number.isNaN(fd)) {
    process.stderr.write(
      `[inquirer-ai] Warning: invalid INQUIRER_AI_FD_OUT="${fdOut}", falling back to stdout\n`,
    );
    return null;
  }
  return fd;
}

function getInputStream(): NodeJS.ReadableStream {
  const fdIn = process.env.INQUIRER_AI_FD_IN;
  if (fdIn) {
    const fd = parseInt(fdIn, 10);
    if (Number.isNaN(fd)) {
      process.stderr.write(
        `[inquirer-ai] Warning: invalid INQUIRER_AI_FD_IN="${fdIn}", falling back to stdin\n`,
      );
      return process.stdin;
    }
    try {
      return fs.createReadStream("", { fd });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      process.stderr.write(
        `[inquirer-ai] Warning: failed to open fd ${fd} for input: ${msg}, falling back to stdin\n`,
      );
      return process.stdin;
    }
  }
  return process.stdin;
}

let outputFd: number | null = null;
let outputFdResolved = false;

function writeOutput(text: string): void {
  if (!outputFdResolved) {
    outputFd = getOutputFd();
    outputFdResolved = true;
  }
  if (outputFd !== null) {
    // Synchronous write: guarantees the line reaches the OS before any exit so
    // a buffered fd stream cannot drop the final message (R10).
    try {
      fs.writeSync(outputFd, text);
      return;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      process.stderr.write(
        `[inquirer-ai] Warning: failed to write to fd ${outputFd}: ${msg}, falling back to stdout\n`,
      );
      outputFd = null;
    }
  }
  process.stdout.write(text);
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
    for (let waiter = waiters.shift(); waiter; waiter = waiters.shift()) {
      waiter(null);
    }
  });
}

function writeLine(data: Record<string, unknown>): void {
  writeOutput(`${JSON.stringify(data)}\n`);
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

// Advance the logical prompt counter by one and return the new step value.
// Called ONCE per logical prompt; validation re-sends reuse the returned value
// by passing it to agentSend(), so a re-sent prompt keeps the same step (the
// "step" must be identical for a prompt and all of its validation re-sends).
export function agentNextStep(): number {
  agentStep++;
  return agentStep;
}

export async function agentSend(
  payload: Record<string, unknown>,
  step: number,
): Promise<void> {
  if (!handshakeSent) {
    sendHandshake();
  }
  writeLine({ kind: "prompt", step, total: null, ...payload });
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
      const raw: unknown = JSON.parse(line);
      if (typeof raw !== "object" || raw === null) {
        throw new SyntaxError("not an object");
      }
      resp = raw as Record<string, unknown>;
    } catch {
      throw new Error(
        `Invalid JSON response: ${line.trim()}. Expected JSON like: {"answer": "<value>"}`,
      );
    }
    if (resp.kind === "handshake_ack") {
      handshakeAck = resp;
      continue;
    }
    if (!("answer" in resp)) {
      throw new Error(
        `Response must be a JSON object with an "answer" key, ` +
          `e.g. {"answer": "<value>"}. Got: ${line.trim()}`,
      );
    }
    // Return the raw answer value; the caller (BasePrompt.executeAgent) passes it
    // through validateAnswer() which narrows it to the prompt's concrete type T.
    return resp.answer;
  }
}
