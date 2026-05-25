import { Readable, Writable } from "node:stream";
import { describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { SelectPrompt } from "../src/prompts/select.js";
import { TextPrompt } from "../src/prompts/text.js";
import { resetSocketTransport } from "../src/socket.js";

const ACK = '{"kind":"handshake_ack"}';

function setup(answers: string[]) {
  resetAgent();
  resetSocketTransport();
  vi.stubEnv("INQUIRER_AI_MODE", "agent");
  vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  const stdin = Readable.from(answers.map((a) => `${a}\n`).join(""));
  const writable = new Writable({
    write(_c: Buffer, _e: string, cb: () => void) { cb(); },
  });
  const origStdin = process.stdin;
  const origStdout = process.stdout;
  Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
  Object.defineProperty(process, "stdout", { value: writable, configurable: true });
  return () => {
    Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
  };
}

describe("Chaos tests", () => {
  it("garbage JSON", async () => {
    const restore = setup([ACK, "not json at all"]);
    try {
      await expect(new TextPrompt({ message: "x" }).execute()).rejects.toThrow();
    } finally {
      restore();
    }
  });

  it("empty JSON object (no answer key)", async () => {
    const restore = setup([ACK, "{}"]);
    try {
      await expect(new TextPrompt({ message: "x" }).execute()).rejects.toThrow("answer");
    } finally {
      restore();
    }
  });

  it("JSON array instead of object", async () => {
    const restore = setup([ACK, "[1,2,3]"]);
    try {
      await expect(new TextPrompt({ message: "x" }).execute()).rejects.toThrow();
    } finally {
      restore();
    }
  });

  it("very long string answer (100K chars)", async () => {
    const longStr = "a".repeat(100_000);
    const restore = setup([ACK, `{"answer": "${longStr}"}`]);
    try {
      const result = await new TextPrompt({ message: "x" }).execute();
      expect(result.length).toBe(100_000);
    } finally {
      restore();
    }
  });

  it("unicode bomb answer", async () => {
    const unicode = "\u{1f389}".repeat(1000);
    const restore = setup([ACK, JSON.stringify({ answer: unicode })]);
    try {
      const result = await new TextPrompt({ message: "x" }).execute();
      expect(result).toBe(unicode);
    } finally {
      restore();
    }
  });

  it("null answer to number without default", async () => {
    // With retries, need 4 null answers to exhaust retries
    const restore = setup([
      ACK,
      '{"answer": null}',
      '{"answer": null}',
      '{"answer": null}',
      '{"answer": null}',
    ]);
    try {
      await expect(
        new NumberPrompt({ message: "x" }).execute(),
      ).rejects.toThrow();
    } finally {
      restore();
    }
  });

  it("boolean answer to number", async () => {
    const restore = setup([
      ACK,
      '{"answer": true}',
      '{"answer": true}',
      '{"answer": true}',
      '{"answer": true}',
    ]);
    try {
      await expect(
        new NumberPrompt({ message: "x" }).execute(),
      ).rejects.toThrow("Expected a number");
    } finally {
      restore();
    }
  });

  it("nested JSON in answer", async () => {
    const restore = setup([ACK, '{"answer": {"nested": "object"}}']);
    try {
      const result = await new TextPrompt({ message: "x" }).execute();
      expect(result).toBe("[object Object]");
    } finally {
      restore();
    }
  });

  it("empty stdin (EOF)", async () => {
    const restore = setup([]);
    try {
      await expect(new TextPrompt({ message: "x" }).execute()).rejects.toThrow("stdin closed");
    } finally {
      restore();
    }
  });

  it("select with unicode choice names", async () => {
    const restore = setup([ACK, '{"answer": "日本語"}']);
    try {
      const result = await new SelectPrompt({
        message: "x",
        choices: ["English", "日本語", "中文"],
      }).execute();
      expect(result).toBe("日本語");
    } finally {
      restore();
    }
  });

  it("checkbox with empty array", async () => {
    const restore = setup([ACK, '{"answer": []}']);
    try {
      const result = await new CheckboxPrompt({
        message: "x",
        choices: ["a", "b"],
      }).execute();
      expect(result).toEqual([]);
    } finally {
      restore();
    }
  });

  it("number with string representation", async () => {
    const restore = setup([ACK, '{"answer": "42"}']);
    try {
      const result = await new NumberPrompt({ message: "x" }).execute();
      expect(result).toBe(42);
    } finally {
      restore();
    }
  });

  it("number with float string", async () => {
    const restore = setup([ACK, '{"answer": "3.14"}']);
    try {
      const result = await new NumberPrompt({ message: "x" }).execute();
      expect(result).toBeCloseTo(3.14);
    } finally {
      restore();
    }
  });

  it("extra fields in response are ignored", async () => {
    const restore = setup([ACK, '{"answer": "hello", "extra": "ignored", "meta": 42}']);
    try {
      const result = await new TextPrompt({ message: "x" }).execute();
      expect(result).toBe("hello");
    } finally {
      restore();
    }
  });
});
