import * as readline from "node:readline";
import { Writable } from "node:stream";
import { ansi, BOLD, getTheme, RESET } from "./theme.js";

export async function readLine(prompt: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
    terminal: true,
  });
  try {
    return await new Promise<string>((resolve) => {
      rl.question(prompt, (answer) => resolve(answer));
    });
  } finally {
    rl.close();
  }
}

export async function readPassword(prompt: string, mask?: string | null): Promise<string> {
  const mutableOutput = new Writable({
    write(_chunk, _encoding, callback) {
      callback();
    },
  });

  const rl = readline.createInterface({
    input: process.stdin,
    output: mutableOutput,
    terminal: true,
  });

  process.stderr.write(prompt);

  return new Promise<string>((resolve) => {
    const chars: string[] = [];
    process.stdin.setRawMode(true);
    process.stdin.resume();

    const onData = (buf: Buffer): void => {
      const ch = buf.toString("utf8");
      if (ch === "\r" || ch === "\n") {
        process.stdin.setRawMode(false);
        process.stdin.removeListener("data", onData);
        process.stderr.write("\n");
        rl.close();
        resolve(chars.join(""));
        return;
      }
      if (ch === "\x03") {
        process.stdin.setRawMode(false);
        process.stdin.removeListener("data", onData);
        rl.close();
        process.stderr.write("\n");
        resolve("");
        return;
      }
      if (ch === "\x7f" || ch === "\b") {
        if (chars.length > 0) {
          chars.pop();
          if (mask) {
            process.stderr.write("\b \b");
          }
        }
        return;
      }
      chars.push(ch);
      if (mask) {
        process.stderr.write(mask);
      }
    };
    process.stdin.on("data", onData);
  });
}

export function formatQuestion(message: string, suffix = ""): string {
  const t = getTheme();
  return `${ansi(t.question)}${t.symQuestion}${RESET} ${BOLD}${message}${suffix}:${RESET} `;
}

export function formatSuccess(message: string, answer: string): string {
  const t = getTheme();
  return `${ansi(t.success)}${t.symSuccess}${RESET} ${message} ${ansi(t.answer)}${answer}${RESET}`;
}

export function formatError(msg: string): string {
  const t = getTheme();
  return `${ansi(t.error)}  ${msg}${RESET}`;
}

export interface ListItem {
  text: string;
  style: string;
}

export interface ListConfig {
  message: string;
  getItems: () => ListItem[];
  onKey: (key: string) => { done: false } | { done: true; result: unknown };
}

export async function runListPrompt(config: ListConfig): Promise<unknown> {
  const { stdin } = process;
  if (!stdin.setRawMode) throw new Error("Terminal does not support raw mode");

  stdin.setRawMode(true);
  stdin.resume();
  stdin.setEncoding("utf8");

  let renderedLines = 0;

  const render = (): void => {
    if (renderedLines > 0) {
      process.stderr.write(`\x1b[${renderedLines}A`);
    }
    const t = getTheme();
    const header = `${ansi(t.question)}${t.symQuestion}${RESET} ${BOLD}${config.message}${RESET}`;
    const items = config.getItems();
    const lines = [header, ...items.map((it) => `${it.style}${it.text}${RESET}`)];
    for (let i = 0; i < lines.length; i++) {
      process.stderr.write(`\x1b[2K${lines[i]!}\n`);
    }
    if (renderedLines > lines.length) {
      for (let i = lines.length; i < renderedLines; i++) {
        process.stderr.write("\x1b[2K\n");
      }
      process.stderr.write(`\x1b[${renderedLines - lines.length}A`);
    }
    renderedLines = lines.length;
  };

  process.stderr.write("\x1b[?25l");
  render();

  return new Promise<unknown>((resolve) => {
    const onData = (data: Buffer | string): void => {
      const key = parseKey(typeof data === "string" ? data : data.toString("utf8"));
      const result = config.onKey(key);
      if (result.done) {
        stdin.setRawMode(false);
        stdin.removeListener("data", onData);
        stdin.pause();
        process.stderr.write("\x1b[?25h");
        if (renderedLines > 0) {
          process.stderr.write(`\x1b[${renderedLines}A`);
          for (let i = 0; i < renderedLines; i++) {
            process.stderr.write("\x1b[2K\n");
          }
          process.stderr.write(`\x1b[${renderedLines}A`);
        }
        resolve(result.result);
      } else {
        render();
      }
    };
    stdin.on("data", onData);
  });
}

function parseKey(data: string): string {
  if (data === "\x1b[A") return "up";
  if (data === "\x1b[B") return "down";
  if (data === "\r" || data === "\n") return "enter";
  if (data === " ") return "space";
  if (data === "\x03") return "ctrl-c";
  if (data === "\x1b[H" || data === "\x1b[1~") return "home";
  if (data === "\x1b[F" || data === "\x1b[4~") return "end";
  if (data.length === 1) return data;
  return "";
}
