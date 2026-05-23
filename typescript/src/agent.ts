import * as readline from "node:readline";

const VERSION = "0.1.0";

let handshakeSent = false;
let rl: readline.Interface | null = null;
let lineBuffer: string[] = [];
let waiters: Array<(line: string | null) => void> = [];
let closed = false;

export function resetAgent(): void {
  handshakeSent = false;
  if (rl) {
    rl.removeAllListeners();
    rl.close();
    rl = null;
  }
  lineBuffer = [];
  waiters = [];
  closed = false;
}

function ensureRL(): void {
  if (rl) return;
  closed = false;
  rl = readline.createInterface({ input: process.stdin, terminal: false });
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

function sendHandshake(): void {
  if (handshakeSent) return;
  handshakeSent = true;
  const meta = {
    protocol: "inquirer-ai",
    version: VERSION,
    format: "jsonl",
    interaction: "sequential",
    description:
      "Interactive prompt protocol. Prompts are sent one at a time — " +
      "read one JSON line from stdout, respond with one JSON line on stdin, " +
      "then wait for the next prompt. Do NOT send all answers at once. " +
      "Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication.",
    example_response: { answer: "<value>" },
  };
  process.stdout.write(JSON.stringify(meta) + "\n");
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

export function agentSend(payload: Record<string, unknown>): void {
  sendHandshake();
  process.stdout.write(JSON.stringify(payload) + "\n");
}

export async function agentReceive(): Promise<unknown> {
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
  if (typeof resp !== "object" || resp === null || !("answer" in resp)) {
    throw new Error(
      `Response must be a JSON object with an "answer" key, ` +
        `e.g. {"answer": "<value>"}. Got: ${line.trim()}`,
    );
  }
  return resp["answer"];
}
