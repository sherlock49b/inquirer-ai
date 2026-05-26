import { Readable, Writable } from "node:stream";
import fc from "fast-check";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { agentReceive, agentSendValidationError, resetAgent } from "../src/agent.js";
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
import { resetSocketTransport } from "../src/socket.js";
import { VERSION } from "../src/version.js";

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

function withMockedStdio(
  stdinLines: string[],
  fn: (chunks: string[]) => Promise<void>,
): Promise<void> {
  const { chunks, writable } = captureStdout();
  const stdin = makeStdinFromLines(stdinLines);
  const origStdin = process.stdin;
  const origStdout = process.stdout;
  Object.defineProperty(process, "stdin", { value: stdin, configurable: true });
  Object.defineProperty(process, "stdout", { value: writable, configurable: true });
  return fn(chunks).finally(() => {
    Object.defineProperty(process, "stdin", { value: origStdin, configurable: true });
    Object.defineProperty(process, "stdout", { value: origStdout, configurable: true });
  });
}

function parseOutputLines(chunks: string[]): Record<string, unknown>[] {
  const output = chunks.join("");
  return output
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

// ---------------------------------------------------------------------------
// 1. Handshake format
// ---------------------------------------------------------------------------
describe("Protocol contract: Handshake format", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  it("first JSONL line is a well-formed handshake", async () => {
    await withMockedStdio([ACK, '{"answer": "x"}'], async (chunks) => {
      await new TextPrompt({ message: "Q?" }).execute();
      const lines = parseOutputLines(chunks);
      const hs = lines[0]!;

      expect(hs.kind).toBe("handshake");
      expect(hs.protocol).toBe("inquirer-ai");
      expect(hs.version).toBe(VERSION);
      expect(hs.format).toBe("jsonl");
      expect(hs.interaction).toBe("sequential");
      expect(hs.total).toBeNull();
      expect(hs.description).toEqual(expect.any(String));
      expect((hs.description as string).length).toBeGreaterThan(0);
      expect(hs.example_response).toEqual({ answer: "<value>" });
    });
  });

  it("handshake version matches VERSION from version.ts", async () => {
    expect(VERSION).toMatch(/^\d+\.\d+\.\d+/);
    await withMockedStdio([ACK, '{"answer": "x"}'], async (chunks) => {
      await new TextPrompt({ message: "Q?" }).execute();
      const hs = parseOutputLines(chunks)[0]!;
      expect(hs.version).toBe(VERSION);
    });
  });

  it("handshake is emitted exactly once across multiple prompts", async () => {
    await withMockedStdio(
      [ACK, '{"answer": "a"}', '{"answer": "b"}'],
      async (chunks) => {
        await new TextPrompt({ message: "Q1?" }).execute();
        await new TextPrompt({ message: "Q2?" }).execute();
        const lines = parseOutputLines(chunks);
        const handshakes = lines.filter((l) => l.kind === "handshake");
        expect(handshakes.length).toBe(1);
      },
    );
  });
});

// ---------------------------------------------------------------------------
// 2. Prompt format per type
// ---------------------------------------------------------------------------
describe("Protocol contract: Prompt format per type", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  function verifyCommonPromptFields(
    prompt: Record<string, unknown>,
    expectedType: string,
    expectedMessage: string,
  ): void {
    expect(prompt.kind).toBe("prompt");
    expect(prompt.type).toBe(expectedType);
    expect(prompt.message).toBe(expectedMessage);
    expect(prompt.step).toEqual(expect.any(Number));
    expect(prompt.step).toBeGreaterThanOrEqual(1);
    expect(prompt.total).toBeNull();
  }

  it("TextPrompt: type=input, message, default", async () => {
    await withMockedStdio([ACK, '{"answer": "hi"}'], async (chunks) => {
      await new TextPrompt({ message: "Name?", default: "world" }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "input", "Name?");
      expect(p.default).toBe("world");
    });
  });

  it("ConfirmPrompt: type=confirm, message", async () => {
    await withMockedStdio([ACK, '{"answer": true}'], async (chunks) => {
      await new ConfirmPrompt({ message: "Sure?" }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "confirm", "Sure?");
    });
  });

  it("SelectPrompt: type=select, message, choices", async () => {
    await withMockedStdio([ACK, '{"answer": "a"}'], async (chunks) => {
      await new SelectPrompt({
        message: "Pick?",
        choices: ["a", "b"],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "select", "Pick?");
      expect(p.choices).toEqual(expect.any(Array));
      expect((p.choices as unknown[]).length).toBe(2);
    });
  });

  it("CheckboxPrompt: type=checkbox, message, choices", async () => {
    await withMockedStdio([ACK, '{"answer": ["a"]}'], async (chunks) => {
      await new CheckboxPrompt({
        message: "Choose?",
        choices: ["a", "b", "c"],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "checkbox", "Choose?");
      expect(p.choices).toEqual(expect.any(Array));
      expect((p.choices as unknown[]).length).toBe(3);
    });
  });

  it("NumberPrompt: type=number, message, min, max, float_allowed, num_step", async () => {
    await withMockedStdio([ACK, '{"answer": 42}'], async (chunks) => {
      await new NumberPrompt({
        message: "Port?",
        min: 1,
        max: 65535,
        floatAllowed: false,
        step: 1,
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "number", "Port?");
      expect(p.min).toBe(1);
      expect(p.max).toBe(65535);
      expect(p.float_allowed).toBe(false);
      expect(p.num_step).toBe(1);
    });
  });

  it("PasswordPrompt: type=password, message, mask", async () => {
    await withMockedStdio([ACK, '{"answer": "s3cret"}'], async (chunks) => {
      await new PasswordPrompt({ message: "Token?", mask: "#" }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "password", "Token?");
      expect(p.mask).toBe("#");
    });
  });

  it("EditorPrompt: type=editor, message, postfix", async () => {
    await withMockedStdio([ACK, '{"answer": "text"}'], async (chunks) => {
      await new EditorPrompt({ message: "Body?", postfix: ".md" }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "editor", "Body?");
      expect(p.postfix).toBe(".md");
    });
  });

  it("ExpandPrompt: type=expand, message, choices with key/name/value", async () => {
    await withMockedStdio([ACK, '{"answer": "y"}'], async (chunks) => {
      await new ExpandPrompt({
        message: "Overwrite?",
        choices: [
          { key: "y", name: "Yes", value: "yes" },
          { key: "n", name: "No", value: "no" },
        ],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "expand", "Overwrite?");
      const choices = p.choices as { key: string; name: string; value: string }[];
      expect(choices.length).toBe(2);
      expect(choices[0]).toEqual({ key: "y", name: "Yes", value: "yes" });
      expect(choices[1]).toEqual({ key: "n", name: "No", value: "no" });
    });
  });

  it("RawlistPrompt: type=rawlist, message, choices", async () => {
    await withMockedStdio([ACK, '{"answer": 1}'], async (chunks) => {
      await new RawlistPrompt({
        message: "Version?",
        choices: ["3.13", "3.12"],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "rawlist", "Version?");
      expect(p.choices).toEqual(expect.any(Array));
      expect((p.choices as unknown[]).length).toBe(2);
    });
  });

  it("PathPrompt: type=path, message, only_directories", async () => {
    await withMockedStdio([ACK, '{"answer": "/tmp"}'], async (chunks) => {
      await new PathPrompt({
        message: "Dir?",
        onlyDirectories: true,
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "path", "Dir?");
      expect(p.only_directories).toBe(true);
    });
  });

  it("AutocompletePrompt: type=autocomplete, message, choices", async () => {
    await withMockedStdio([ACK, '{"answer": "Go"}'], async (chunks) => {
      await new AutocompletePrompt({
        message: "Lang?",
        choices: ["Go", "Rust"],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "autocomplete", "Lang?");
      expect(p.choices).toEqual(["Go", "Rust"]);
    });
  });

  it("SearchPrompt: type=search, message, searchable, choices", async () => {
    await withMockedStdio([ACK, '{"answer": "httpx"}'], async (chunks) => {
      await new SearchPrompt({
        message: "Pkg?",
        source: () => [
          { name: "requests", value: "requests" },
          { name: "httpx", value: "httpx" },
        ],
      }).execute();
      const lines = parseOutputLines(chunks);
      const p = lines[1]!;
      verifyCommonPromptFields(p, "search", "Pkg?");
      expect(p.searchable).toBe(true);
      expect(p.choices).toEqual(expect.any(Array));
    });
  });
});

// ---------------------------------------------------------------------------
// 3. Validation error format
// ---------------------------------------------------------------------------
describe("Protocol contract: Validation error format", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  it("validation_error line has kind and message", async () => {
    await withMockedStdio(
      [ACK, '{"answer": "invalid"}', '{"answer": "go"}'],
      async (chunks) => {
        await new SelectPrompt({
          message: "Lang?",
          choices: ["python", "go"],
        }).execute();
        const lines = parseOutputLines(chunks);
        const errors = lines.filter((l) => l.kind === "validation_error");
        expect(errors.length).toBeGreaterThanOrEqual(1);
        const err = errors[0]!;
        expect(err.kind).toBe("validation_error");
        expect(err.message).toEqual(expect.any(String));
        expect((err.message as string).length).toBeGreaterThan(0);
      },
    );
  });

  it("agentSendValidationError outputs correct format", async () => {
    await withMockedStdio([], async (chunks) => {
      agentSendValidationError("bad input");
      const output = chunks.join("").trim();
      const parsed = JSON.parse(output);
      expect(parsed).toEqual({
        kind: "validation_error",
        message: "bad input",
      });
    });
  });

  it("NumberPrompt validation error for out-of-range includes helpful message", async () => {
    await withMockedStdio(
      [ACK, '{"answer": 0}', '{"answer": 5}'],
      async (chunks) => {
        await new NumberPrompt({
          message: "Port?",
          min: 1,
          max: 100,
        }).execute();
        const lines = parseOutputLines(chunks);
        const errors = lines.filter((l) => l.kind === "validation_error");
        expect(errors.length).toBeGreaterThanOrEqual(1);
        expect(errors[0]!.message).toContain("at least 1");
      },
    );
  });
});

// ---------------------------------------------------------------------------
// 4. Answer extraction (agentReceive)
// ---------------------------------------------------------------------------
describe("Protocol contract: Answer extraction", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  it("agentReceive extracts answer from valid JSON", async () => {
    await withMockedStdio(['{"answer": "hello"}'], async () => {
      const answer = await agentReceive();
      expect(answer).toBe("hello");
    });
  });

  it("agentReceive extracts numeric answer", async () => {
    await withMockedStdio(['{"answer": 42}'], async () => {
      const answer = await agentReceive();
      expect(answer).toBe(42);
    });
  });

  it("agentReceive extracts null answer", async () => {
    await withMockedStdio(['{"answer": null}'], async () => {
      const answer = await agentReceive();
      expect(answer).toBeNull();
    });
  });

  it("agentReceive extracts array answer", async () => {
    await withMockedStdio(['{"answer": ["a", "b"]}'], async () => {
      const answer = await agentReceive();
      expect(answer).toEqual(["a", "b"]);
    });
  });

  it("agentReceive rejects invalid JSON", async () => {
    await withMockedStdio(["not-json"], async () => {
      await expect(agentReceive()).rejects.toThrow("Invalid JSON response");
    });
  });

  it("agentReceive rejects JSON without answer key", async () => {
    await withMockedStdio(['{"value": "x"}'], async () => {
      await expect(agentReceive()).rejects.toThrow('"answer"');
    });
  });

  it("agentReceive rejects non-object JSON (array)", async () => {
    // Arrays pass typeof === "object" check but lack "answer" key,
    // so agentReceive rejects with the missing-key error, not "Invalid JSON".
    await withMockedStdio(["[1,2,3]"], async () => {
      await expect(agentReceive()).rejects.toThrow('"answer"');
    });
  });

  it("agentReceive rejects non-object JSON (string)", async () => {
    await withMockedStdio(['"hello"'], async () => {
      await expect(agentReceive()).rejects.toThrow("Invalid JSON response");
    });
  });

  it("agentReceive throws on closed stdin", async () => {
    // Empty stream: no lines, stdin closes immediately
    await withMockedStdio([], async () => {
      await expect(agentReceive()).rejects.toThrow("stdin closed");
    });
  });

  it("agentReceive skips handshake_ack lines", async () => {
    await withMockedStdio(
      [ACK, '{"answer": "real"}'],
      async () => {
        const answer = await agentReceive();
        expect(answer).toBe("real");
      },
    );
  });
});

// ---------------------------------------------------------------------------
// 5. Property-based (fast-check)
// ---------------------------------------------------------------------------
describe("Protocol contract: Property-based tests", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  it("TextPrompt toAgentDict always has required fields for random messages", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 200 }),
        async (msg) => {
          resetAgent();
          resetSocketTransport();
          await withMockedStdio([ACK, '{"answer": "x"}'], async (chunks) => {
            await new TextPrompt({ message: msg }).execute();
            const lines = parseOutputLines(chunks);
            expect(lines.length).toBeGreaterThanOrEqual(2);
            const hs = lines[0]!;
            expect(hs.kind).toBe("handshake");
            expect(hs.protocol).toBe("inquirer-ai");
            expect(hs.version).toBe(VERSION);

            const p = lines[1]!;
            expect(p.kind).toBe("prompt");
            expect(p.type).toBe("input");
            expect(p.message).toBe(msg);
            expect(typeof p.step).toBe("number");
            expect(p.total).toBeNull();
          });
        },
      ),
      { numRuns: 50 },
    );
  });

  it("ConfirmPrompt toAgentDict always has required fields for random messages", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 200 }),
        async (msg) => {
          resetAgent();
          resetSocketTransport();
          await withMockedStdio([ACK, '{"answer": true}'], async (chunks) => {
            await new ConfirmPrompt({ message: msg }).execute();
            const lines = parseOutputLines(chunks);
            const p = lines[1]!;
            expect(p.kind).toBe("prompt");
            expect(p.type).toBe("confirm");
            expect(p.message).toBe(msg);
            expect(typeof p.step).toBe("number");
            expect(p.total).toBeNull();
          });
        },
      ),
      { numRuns: 50 },
    );
  });

  it("NumberPrompt toAgentDict always has required fields for random messages", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 200 }),
        async (msg) => {
          resetAgent();
          resetSocketTransport();
          await withMockedStdio([ACK, '{"answer": 1}'], async (chunks) => {
            await new NumberPrompt({ message: msg }).execute();
            const lines = parseOutputLines(chunks);
            const p = lines[1]!;
            expect(p.kind).toBe("prompt");
            expect(p.type).toBe("number");
            expect(p.message).toBe(msg);
            expect(typeof p.step).toBe("number");
            expect(p.total).toBeNull();
            // NumberPrompt always includes these fields
            expect("min" in p).toBe(true);
            expect("max" in p).toBe(true);
            expect("float_allowed" in p).toBe(true);
          });
        },
      ),
      { numRuns: 50 },
    );
  });

  it("PasswordPrompt toAgentDict always has required fields for random messages", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 200 }),
        async (msg) => {
          resetAgent();
          resetSocketTransport();
          await withMockedStdio([ACK, '{"answer": "pw"}'], async (chunks) => {
            await new PasswordPrompt({ message: msg }).execute();
            const lines = parseOutputLines(chunks);
            const p = lines[1]!;
            expect(p.kind).toBe("prompt");
            expect(p.type).toBe("password");
            expect(p.message).toBe(msg);
            expect(typeof p.step).toBe("number");
            expect(p.total).toBeNull();
            expect("mask" in p).toBe(true);
          });
        },
      ),
      { numRuns: 50 },
    );
  });
});
