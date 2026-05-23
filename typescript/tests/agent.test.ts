import { Readable, Writable } from "node:stream";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import { AutocompletePrompt } from "../src/prompts/autocomplete.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { ConfirmPrompt } from "../src/prompts/confirm.js";
import { EditorPrompt } from "../src/prompts/editor.js";
import { ExpandPrompt } from "../src/prompts/expand.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { PasswordPrompt } from "../src/prompts/password.js";
import { PathPrompt } from "../src/prompts/path.js";
import { RawlistPrompt } from "../src/prompts/rawlist.js";
import { SearchPrompt } from "../src/prompts/search.js";
import { SelectPrompt } from "../src/prompts/select.js";
import { TextPrompt } from "../src/prompts/text.js";

const ACK = '{"kind":"handshake_ack"}';

function makeStdinFromLines(lines: string[]): Readable {
  const data = lines.map((l) => `${l}\n`).join("");
  return Readable.from(data);
}

function captureStdout(): { chunks: string[]; writable: Writable } {
  const chunks: string[] = [];
  const writable = new Writable({
    write(chunk: Buffer, _encoding: string, callback: () => void) {
      chunks.push(chunk.toString());
      callback();
    },
  });
  return { chunks, writable };
}

describe("Agent mode prompts (mocked stdin/stdout)", () => {
  beforeEach(() => {
    resetAgent();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
  });

  it("TextPrompt agent sends correct JSON and reads answer", async () => {
    const { chunks, writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "Alice"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new TextPrompt({ message: "Name?" }).execute();
      expect(result).toBe("Alice");

      const output = chunks.join("");
      const lines = output.trim().split("\n");
      expect(lines.length).toBe(2);

      const handshake = JSON.parse(lines[0]!);
      expect(handshake.kind).toBe("handshake");
      expect(handshake.protocol).toBe("inquirer-ai");
      expect(handshake.version).toBe("0.2.0");
      expect(handshake.interaction).toBe("sequential");
      expect(handshake.total).toBeNull();

      const prompt = JSON.parse(lines[1]!);
      expect(prompt.kind).toBe("prompt");
      expect(prompt.step).toBe(1);
      expect(prompt.total).toBeNull();
      expect(prompt.type).toBe("input");
      expect(prompt.message).toBe("Name?");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("ConfirmPrompt coerces string answers", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "yes"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new ConfirmPrompt({ message: "Continue?" }).execute();
      expect(result).toBe(true);
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("SelectPrompt validates choice", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "go"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new SelectPrompt({
        message: "Language?",
        choices: ["python", "go", "rust"],
      }).execute();
      expect(result).toBe("go");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("SelectPrompt rejects invalid choice after retries", async () => {
    const { writable } = captureStdout();
    // Provide enough invalid answers for the retries in executeAgent (3 retries + 1 initial = 4 attempts)
    const stdin = makeStdinFromLines([
      ACK,
      '{"answer": "java"}',
      '{"answer": "java"}',
      '{"answer": "java"}',
      '{"answer": "java"}',
    ]);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      await expect(
        new SelectPrompt({
          message: "Language?",
          choices: ["python", "go"],
        }).execute(),
      ).rejects.toThrow("Invalid choice");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("CheckboxPrompt returns array", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": ["go", "rust"]}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new CheckboxPrompt({
        message: "Languages?",
        choices: ["python", "go", "rust"],
      }).execute();
      expect(result).toEqual(["go", "rust"]);
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("NumberPrompt validates bounds", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": 3000}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new NumberPrompt({
        message: "Port?",
        min: 1024,
        max: 65535,
      }).execute();
      expect(result).toBe(3000);
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("NumberPrompt rejects out of range after retries", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([
      ACK,
      '{"answer": 100}',
      '{"answer": 100}',
      '{"answer": 100}',
      '{"answer": 100}',
    ]);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      await expect(
        new NumberPrompt({
          message: "Port?",
          min: 1024,
        }).execute(),
      ).rejects.toThrow("Must be at least 1024");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("PasswordPrompt returns plain text", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "s3cret"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new PasswordPrompt({ message: "Token?" }).execute();
      expect(result).toBe("s3cret");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("EditorPrompt returns text", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "Hello\\nWorld"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new EditorPrompt({ message: "Description?" }).execute();
      expect(result).toBe("Hello\nWorld");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("RawlistPrompt accepts index", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": 2}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new RawlistPrompt({
        message: "Version?",
        choices: ["3.13", "3.12"],
      }).execute();
      expect(result).toBe("3.12");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("ExpandPrompt accepts key", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "y"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new ExpandPrompt({
        message: "Conflict?",
        choices: [
          { key: "y", name: "Overwrite", value: "overwrite" },
          { key: "n", name: "Skip", value: "skip" },
        ],
      }).execute();
      expect(result).toBe("overwrite");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("PathPrompt returns path", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "/home/user"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new PathPrompt({ message: "Output dir?" }).execute();
      expect(result).toBe("/home/user");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("AutocompletePrompt returns text", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "TypeScript"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new AutocompletePrompt({
        message: "Language?",
        choices: ["Python", "TypeScript", "Go"],
      }).execute();
      expect(result).toBe("TypeScript");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("SearchPrompt returns value", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "httpx"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new SearchPrompt({
        message: "Package?",
        source: () => [
          { name: "requests", value: "requests" },
          { name: "httpx", value: "httpx" },
        ],
      }).execute();
      expect(result).toBe("httpx");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("TextPrompt uses default when answer is null", async () => {
    const { writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": null}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new TextPrompt({
        message: "Name?",
        default: "World",
      }).execute();
      expect(result).toBe("World");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("handshake is sent only once across multiple prompts", async () => {
    const { chunks, writable } = captureStdout();
    const stdin = makeStdinFromLines([ACK, '{"answer": "A"}', '{"answer": "B"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      await new TextPrompt({ message: "Q1?" }).execute();
      await new TextPrompt({ message: "Q2?" }).execute();

      const output = chunks.join("");
      const lines = output.trim().split("\n");
      expect(lines.length).toBe(3);

      const handshake = JSON.parse(lines[0]!);
      expect(handshake.kind).toBe("handshake");
      expect(handshake.protocol).toBe("inquirer-ai");

      const p1 = JSON.parse(lines[1]!);
      expect(p1.kind).toBe("prompt");
      expect(p1.step).toBe(1);
      expect(p1.type).toBe("input");
      expect(p1.message).toBe("Q1?");

      const p2 = JSON.parse(lines[2]!);
      expect(p2.kind).toBe("prompt");
      expect(p2.step).toBe(2);
      expect(p2.type).toBe("input");
      expect(p2.message).toBe("Q2?");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });

  it("handshake buffers answer line when no ack is sent", async () => {
    const { writable } = captureStdout();
    // No ACK line - first line is the answer itself
    const stdin = makeStdinFromLines(['{"answer": "Alice"}']);

    const origStdin = process.stdin;
    const origStdout = process.stdout;
    Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: writable, configurable: true });

    try {
      const result = await new TextPrompt({ message: "Name?" }).execute();
      expect(result).toBe("Alice");
    } finally {
      Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
      Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
    }
  });
});
