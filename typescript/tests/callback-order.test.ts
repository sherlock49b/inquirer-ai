/**
 * Tests for the callback execution order invariant: validate -> filter.
 *
 * The critical invariant is:
 *   1. Built-in validation runs first (validateAnswer)
 *   2. User-provided validate callback runs second
 *   3. Filter runs LAST, only on accepted values
 */

import { Readable, Writable } from "node:stream";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import { ValidationError } from "../src/errors.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { ExpandPrompt } from "../src/prompts/expand.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { SelectPrompt } from "../src/prompts/select.js";
import { TextPrompt } from "../src/prompts/text.js";
import { resetSocketTransport } from "../src/socket.js";

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

function setupAgentMode(answers: string[]) {
  resetAgent();
  resetSocketTransport();
  vi.stubEnv("INQUIRER_AI_MODE", "agent");
  vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");

  const { writable } = captureStdout();
  const stdin = makeStdinFromLines([ACK, ...answers]);

  const origStdin = process.stdin;
  const origStdout = process.stdout;
  Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
  Object.defineProperty(process, "stdout", { value: writable, configurable: true });

  return () => {
    Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
  };
}

describe("Callback order invariant: validate -> filter", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
  });

  // ── Test 1: Order invariant — validate is called before filter ──

  describe("Order invariant", () => {
    it("Text: validate runs before filter", async () => {
      const cleanup = setupAgentMode(['{"answer":"hello"}']);
      try {
        const log: string[] = [];
        const result = await new TextPrompt({
          message: "Q",
          validate: (_v: string) => { log.push("validate"); return true; },
          filter: (v: string) => { log.push("filter"); return v; },
        }).execute();
        expect(result).toBe("hello");
        expect(log).toEqual(["validate", "filter"]);
      } finally {
        cleanup();
      }
    });

    it("Number: validate runs before filter", async () => {
      const cleanup = setupAgentMode(['{"answer":42}']);
      try {
        const log: string[] = [];
        const result = await new NumberPrompt({
          message: "Q",
          validate: (_v: number) => { log.push("validate"); return true; },
          filter: (v: number) => { log.push("filter"); return v; },
        }).execute();
        expect(result).toBe(42);
        expect(log).toEqual(["validate", "filter"]);
      } finally {
        cleanup();
      }
    });

    it("Select: validate runs before filter", async () => {
      const cleanup = setupAgentMode(['{"answer":"a"}']);
      try {
        const log: string[] = [];
        const result = await new SelectPrompt({
          message: "Q",
          choices: [{ name: "A", value: "a" }],
          validate: (_v: unknown) => { log.push("validate"); return true; },
          filter: (v: unknown) => { log.push("filter"); return v; },
        }).execute();
        expect(result).toBe("a");
        expect(log).toEqual(["validate", "filter"]);
      } finally {
        cleanup();
      }
    });

    it("Expand: validate runs before filter", async () => {
      const cleanup = setupAgentMode(['{"answer":"y"}']);
      try {
        const log: string[] = [];
        const result = await new ExpandPrompt({
          message: "Q",
          choices: [{ key: "y", name: "Yes", value: "yes" }],
          validate: (_v: unknown) => { log.push("validate"); return true; },
          filter: (v: unknown) => { log.push("filter"); return v; },
        }).execute();
        expect(result).toBe("yes");
        expect(log).toEqual(["validate", "filter"]);
      } finally {
        cleanup();
      }
    });

    it("Checkbox: validate runs before filter", async () => {
      const cleanup = setupAgentMode(['{"answer":["a"]}']);
      try {
        const log: string[] = [];
        const result = await new CheckboxPrompt({
          message: "Q",
          choices: [{ name: "A", value: "a" }],
          validate: (_v: unknown[]) => { log.push("validate"); return true; },
          filter: (v: unknown[]) => { log.push("filter"); return v; },
        }).execute();
        expect(result).toEqual(["a"]);
        expect(log).toEqual(["validate", "filter"]);
      } finally {
        cleanup();
      }
    });
  });

  // ── Test 2: Filter NOT called when validate rejects ──

  describe("Filter skipped on rejection", () => {
    it("Text: filter not called when validate rejects", async () => {
      const cleanup = setupAgentMode([
        '{"answer":"bad"}',
        '{"answer":"bad"}',
        '{"answer":"bad"}',
        '{"answer":"bad"}',
      ]);
      try {
        const filterCalls: string[] = [];
        await expect(
          new TextPrompt({
            message: "Q",
            validate: () => "rejected",
            filter: (v: string) => { filterCalls.push(v); return v; },
          }).execute(),
        ).rejects.toThrow(ValidationError);
        expect(filterCalls).toEqual([]);
      } finally {
        cleanup();
      }
    });

    it("Number: filter not called when validate rejects", async () => {
      const cleanup = setupAgentMode([
        '{"answer":42}',
        '{"answer":42}',
        '{"answer":42}',
        '{"answer":42}',
      ]);
      try {
        const filterCalls: number[] = [];
        await expect(
          new NumberPrompt({
            message: "Q",
            validate: () => "rejected",
            filter: (v: number) => { filterCalls.push(v); return v; },
          }).execute(),
        ).rejects.toThrow(ValidationError);
        expect(filterCalls).toEqual([]);
      } finally {
        cleanup();
      }
    });

    it("Number: filter not called when built-in validation rejects (out of range)", async () => {
      const cleanup = setupAgentMode([
        '{"answer":100}',
        '{"answer":100}',
        '{"answer":100}',
        '{"answer":100}',
      ]);
      try {
        const filterCalls: number[] = [];
        const validateCalls: number[] = [];
        await expect(
          new NumberPrompt({
            message: "Q",
            min: 0,
            max: 10,
            validate: (v: number) => { validateCalls.push(v); return true; },
            filter: (v: number) => { filterCalls.push(v); return v; },
          }).execute(),
        ).rejects.toThrow(ValidationError);
        expect(filterCalls).toEqual([]);
        expect(validateCalls).toEqual([]);
      } finally {
        cleanup();
      }
    });
  });

  // ── Test 3: Filter receives raw value ──

  describe("Filter sees raw value", () => {
    it("Text: filter receives original value", async () => {
      const cleanup = setupAgentMode(['{"answer":"  HELLO  "}']);
      try {
        const received: string[] = [];
        const result = await new TextPrompt({
          message: "Q",
          validate: () => true,
          filter: (v: string) => { received.push(v); return v.trim(); },
        }).execute();
        expect(received).toEqual(["  HELLO  "]);
        expect(result).toBe("HELLO");
      } finally {
        cleanup();
      }
    });

    it("Number: filter receives validated number", async () => {
      const cleanup = setupAgentMode(['{"answer":42}']);
      try {
        const received: number[] = [];
        const result = await new NumberPrompt({
          message: "Q",
          validate: () => true,
          filter: (v: number) => { received.push(v); return v * 2; },
        }).execute();
        expect(received).toEqual([42]);
        expect(result).toBe(84);
      } finally {
        cleanup();
      }
    });
  });

  // ── Test 4: Multiple rejections, filter called only once ──

  describe("Multiple rejections", () => {
    it("Text: filter called only once after retries", async () => {
      const cleanup = setupAgentMode([
        '{"answer":"bad1"}',
        '{"answer":"bad2"}',
        '{"answer":"good"}',
      ]);
      try {
        const filterCalls: string[] = [];
        let attempt = 0;
        const result = await new TextPrompt({
          message: "Q",
          validate: (_v: string) => { attempt++; return attempt > 2 ? true : "rejected"; },
          filter: (v: string) => { filterCalls.push(v); return `${v}_ok`; },
        }).execute();
        expect(filterCalls).toEqual(["good"]);
        expect(result).toBe("good_ok");
      } finally {
        cleanup();
      }
    });

    it("Number: filter called only once after retries", async () => {
      const cleanup = setupAgentMode([
        '{"answer":1}',
        '{"answer":2}',
        '{"answer":3}',
      ]);
      try {
        const filterCalls: number[] = [];
        let attempt = 0;
        const result = await new NumberPrompt({
          message: "Q",
          validate: (_v: number) => { attempt++; return attempt > 2 ? true : "rejected"; },
          filter: (v: number) => { filterCalls.push(v); return v * 10; },
        }).execute();
        expect(filterCalls).toEqual([3]);
        expect(result).toBe(30);
      } finally {
        cleanup();
      }
    });

    it("Select: filter called only once after retries", async () => {
      const cleanup = setupAgentMode([
        '{"answer":"a"}',
        '{"answer":"a"}',
        '{"answer":"a"}',
      ]);
      try {
        const filterCalls: unknown[] = [];
        let attempt = 0;
        await new SelectPrompt({
          message: "Q",
          choices: [{ name: "A", value: "a" }],
          validate: (_v: unknown) => { attempt++; return attempt > 2 ? true : "rejected"; },
          filter: (v: unknown) => { filterCalls.push(v); return v; },
        }).execute();
        expect(filterCalls.length).toBe(1);
      } finally {
        cleanup();
      }
    });
  });

  // ── Test 5: Cross-type consistency ──

  describe("Cross-type consistency", () => {
    const cases = [
      {
        name: "Text",
        answer: '{"answer":"x"}',
        factory: (log: string[]) =>
          new TextPrompt({
            message: "Q",
            validate: () => { log.push("validate"); return true; },
            filter: (v: string) => { log.push("filter"); return v; },
          }),
      },
      {
        name: "Number",
        answer: '{"answer":5}',
        factory: (log: string[]) =>
          new NumberPrompt({
            message: "Q",
            validate: () => { log.push("validate"); return true; },
            filter: (v: number) => { log.push("filter"); return v; },
          }),
      },
      {
        name: "Select",
        answer: '{"answer":"x"}',
        factory: (log: string[]) =>
          new SelectPrompt({
            message: "Q",
            choices: [{ name: "X", value: "x" }],
            validate: () => { log.push("validate"); return true; },
            filter: (v: unknown) => { log.push("filter"); return v; },
          }),
      },
      {
        name: "Expand",
        answer: '{"answer":"y"}',
        factory: (log: string[]) =>
          new ExpandPrompt({
            message: "Q",
            choices: [{ key: "y", name: "Yes", value: "yes" }],
            validate: () => { log.push("validate"); return true; },
            filter: (v: unknown) => { log.push("filter"); return v; },
          }),
      },
      {
        name: "Checkbox",
        answer: '{"answer":["a"]}',
        factory: (log: string[]) =>
          new CheckboxPrompt({
            message: "Q",
            choices: [{ name: "A", value: "a" }],
            validate: () => { log.push("validate"); return true; },
            filter: (v: unknown[]) => { log.push("filter"); return v; },
          }),
      },
    ];

    for (const { name, answer, factory } of cases) {
      it(`${name}: validate -> filter order`, async () => {
        const cleanup = setupAgentMode([answer]);
        try {
          const log: string[] = [];
          await factory(log).execute();
          expect(log).toEqual(["validate", "filter"]);
        } finally {
          cleanup();
        }
      });
    }
  });
});
