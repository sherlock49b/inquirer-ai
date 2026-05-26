/**
 * TUI testing helper for inquirer-ai terminal prompts.
 *
 * Provides a mock stdin/stdout environment that captures rendered output
 * and allows injecting keypresses so prompt code can run without a real
 * terminal.
 */

import { PassThrough } from "node:stream";
import { resetAgent } from "../../src/agent.js";
import { resetSocketTransport } from "../../src/socket.js";

/* ------------------------------------------------------------------ */
/*  ANSI stripping                                                     */
/* ------------------------------------------------------------------ */

// biome-ignore lint/suspicious/noControlCharactersInRegex: ANSI escape sequences require control chars
const ANSI_RE = /[\x1b\x9b]\[[0-9;]*[A-Za-z]|\x1b\[\?25[lh]|\x1b\[2K/g;

function stripAnsi(s: string): string {
  return s.replace(ANSI_RE, "");
}

/* ------------------------------------------------------------------ */
/*  Key-code map                                                       */
/* ------------------------------------------------------------------ */

function keyToData(key: string): string {
  switch (key) {
    case "up":
      return "\x1b[A";
    case "down":
      return "\x1b[B";
    case "enter":
      return "\r";
    case "space":
      return " ";
    case "backspace":
      return "\x7f";
    case "ctrl-c":
      return "\x03";
    case "home":
      return "\x1b[H";
    case "end":
      return "\x1b[F";
    case "tab":
      return "\t";
    default:
      // single character or raw sequence
      return key;
  }
}

/* ------------------------------------------------------------------ */
/*  Public interface                                                    */
/* ------------------------------------------------------------------ */

export interface TuiTestResult<T> {
  /** The promise that resolves with the prompt answer. */
  answer: Promise<T>;
  /** Methods to simulate user interaction. */
  events: {
    /** Send a single key event. Accepts named keys or single characters. */
    keypress(key: string): void;
    /** Type a string of characters, each emitted as a separate keypress. */
    type(text: string): void;
  };
  /** Returns the current rendered output (stderr) with ANSI codes stripped. */
  getScreen(): string;
  /**
   * Returns the full raw captured output (stderr) including ANSI codes.
   * Useful for debugging.
   */
  getScreenRaw(): string;
  /** Clean up resources. Call in afterEach or test teardown. */
  close(): void;
}

/**
 * Render a prompt in a mocked terminal environment and return controls for
 * simulating user interaction and inspecting output.
 *
 * @param factory - A function that creates and executes the prompt, returning
 *                  a promise of the answer. This runs with mocked stdin/stderr.
 *
 * Usage:
 * ```ts
 * const { answer, events } = renderPrompt(() =>
 *   new TextPrompt({ message: "Name?" }).execute(),
 * );
 * events.type("hello");
 * events.keypress("enter");
 * expect(await answer).toBe("hello");
 * ```
 */
export function renderPrompt<T>(
  factory: () => Promise<T>,
): TuiTestResult<T> {
  // --- Save originals ---
  const origStdin = process.stdin;
  const origStderr = process.stderr;

  // --- Reset state so execute() takes the terminal path ---
  resetAgent();
  resetSocketTransport();

  // --- Build mock stdin ---
  // PassThrough in flowing mode acts like a readable stream we can push to.
  const mockStdin = new PassThrough() as PassThrough & {
    setRawMode: (mode: boolean) => void;
    isTTY: boolean;
    setEncoding: (enc: string) => PassThrough;
    pause: () => PassThrough;
    resume: () => PassThrough;
    fd: number;
  };
  mockStdin.isTTY = true;
  mockStdin.setRawMode = () => {};
  // fd is needed for some tty checks
  (mockStdin as any).fd = 0;

  // --- Build mock stderr (capture buffer) ---
  const outputChunks: string[] = [];
  const mockStderr = new PassThrough() as PassThrough & {
    isTTY: boolean;
    columns: number;
    rows: number;
    fd: number;
  };
  mockStderr.isTTY = true;
  mockStderr.columns = 80;
  mockStderr.rows = 24;
  (mockStderr as any).fd = 2;
  mockStderr.on("data", (chunk: Buffer) => {
    outputChunks.push(chunk.toString());
  });

  // --- Install mocks ---
  Object.defineProperty(process, "stdin", {
    value: mockStdin,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(process, "stderr", {
    value: mockStderr,
    configurable: true,
    writable: true,
  });

  // --- Run the prompt ---
  const answerPromise = factory();

  // Ensure cleanup on resolution or rejection
  const cleanedAnswer = answerPromise.finally(() => {
    Object.defineProperty(process, "stdin", {
      value: origStdin,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(process, "stderr", {
      value: origStderr,
      configurable: true,
      writable: true,
    });
  });

  return {
    answer: cleanedAnswer,
    events: {
      keypress(key: string): void {
        const data = keyToData(key);
        mockStdin.write(data);
      },
      type(text: string): void {
        for (const ch of text) {
          mockStdin.write(ch);
        }
      },
    },
    getScreen(): string {
      return stripAnsi(outputChunks.join(""));
    },
    getScreenRaw(): string {
      return outputChunks.join("");
    },
    close(): void {
      try {
        mockStdin.end();
      } catch {
        // ignore
      }
      Object.defineProperty(process, "stdin", {
        value: origStdin,
        configurable: true,
        writable: true,
      });
      Object.defineProperty(process, "stderr", {
        value: origStderr,
        configurable: true,
        writable: true,
      });
    },
  };
}
