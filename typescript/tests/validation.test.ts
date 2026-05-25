import { Readable, Writable } from "node:stream";
import { describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import { InvalidChoiceError, ValidationError } from "../src/errors.js";
import { AutocompletePrompt } from "../src/prompts/autocomplete.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { ConfirmPrompt } from "../src/prompts/confirm.js";
import { EditorPrompt } from "../src/prompts/editor.js";
import { ExpandPrompt } from "../src/prompts/expand.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { PasswordPrompt } from "../src/prompts/password.js";
import { PathPrompt } from "../src/prompts/path.js";
import { RawlistPrompt } from "../src/prompts/rawlist.js";
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

describe("Prompt validation", () => {
  it("TextPrompt returns empty string without default", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(await new TextPrompt({ message: "x" }).execute()).toBe("");
    } finally {
      restore();
    }
  });

  it("ConfirmPrompt coerces truthy strings", async () => {
    for (const val of ["y", "yes", "true", "1", "YES", "True"]) {
      resetAgent();
      const restore = setup([ACK, `{"answer": "${val}"}`]);
      try {
        expect(await new ConfirmPrompt({ message: "x" }).execute()).toBe(true);
      } finally {
        restore();
      }
    }
  });

  it("ConfirmPrompt coerces falsy strings", async () => {
    for (const val of ["n", "no", "false", "0", "anything"]) {
      resetAgent();
      const restore = setup([ACK, `{"answer": "${val}"}`]);
      try {
        const result = await new ConfirmPrompt({ message: "x" }).execute();
        if (["n", "no", "false", "0"].includes(val)) {
          expect(result).toBe(false);
        }
      } finally {
        restore();
      }
    }
  });

  it("ConfirmPrompt default", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(await new ConfirmPrompt({ message: "x", default: true }).execute()).toBe(false);
    } finally {
      restore();
    }
  });

  it("SelectPrompt matches by name", async () => {
    const restore = setup([ACK, '{"answer": "Go"}']);
    try {
      const result = await new SelectPrompt({
        message: "x",
        choices: [{ name: "Go", value: "golang" }],
      }).execute();
      expect(result).toBe("golang");
    } finally {
      restore();
    }
  });

  it("SelectPrompt rejects disabled choice", async () => {
    // 4 attempts total (1 initial + 3 retries) to exhaust retries
    const restore = setup([
      ACK,
      '{"answer": "go"}',
      '{"answer": "go"}',
      '{"answer": "go"}',
      '{"answer": "go"}',
    ]);
    try {
      await expect(
        new SelectPrompt({
          message: "x",
          choices: [
            { name: "Go", value: "go", disabled: true },
            { name: "Rust", value: "rust" },
          ],
        }).execute(),
      ).rejects.toThrow("Invalid choice");
    } finally {
      restore();
    }
  });

  it("SelectPrompt throws on empty choices", () => {
    expect(() => new SelectPrompt({ message: "x", choices: [] })).toThrow(InvalidChoiceError);
  });

  it("SelectPrompt throws when all disabled", () => {
    expect(
      () =>
        new SelectPrompt({
          message: "x",
          choices: [{ name: "A", value: "a", disabled: true }],
        }),
    ).toThrow(InvalidChoiceError);
  });

  it("CheckboxPrompt rejects non-array", async () => {
    const restore = setup([
      ACK,
      '{"answer": "not-array"}',
      '{"answer": "not-array"}',
      '{"answer": "not-array"}',
      '{"answer": "not-array"}',
    ]);
    try {
      await expect(
        new CheckboxPrompt({ message: "x", choices: ["a", "b"] }).execute(),
      ).rejects.toThrow("Expected an array");
    } finally {
      restore();
    }
  });

  it("CheckboxPrompt matches by name", async () => {
    const restore = setup([ACK, '{"answer": ["Go"]}']);
    try {
      const result = await new CheckboxPrompt({
        message: "x",
        choices: [{ name: "Go", value: "golang" }],
      }).execute();
      expect(result).toEqual(["golang"]);
    } finally {
      restore();
    }
  });

  it("NumberPrompt rejects NaN", async () => {
    const restore = setup([
      ACK,
      '{"answer": "abc"}',
      '{"answer": "abc"}',
      '{"answer": "abc"}',
      '{"answer": "abc"}',
    ]);
    try {
      await expect(
        new NumberPrompt({ message: "x" }).execute(),
      ).rejects.toThrow("Not a valid number");
    } finally {
      restore();
    }
  });

  it("NumberPrompt rejects Infinity", async () => {
    const restore = setup([
      ACK,
      '{"answer": "Infinity"}',
      '{"answer": "Infinity"}',
      '{"answer": "Infinity"}',
      '{"answer": "Infinity"}',
    ]);
    try {
      await expect(
        new NumberPrompt({ message: "x" }).execute(),
      ).rejects.toThrow("Not a valid number");
    } finally {
      restore();
    }
  });

  it("NumberPrompt rejects float when not allowed", async () => {
    const restore = setup([
      ACK,
      '{"answer": 3.14}',
      '{"answer": 3.14}',
      '{"answer": 3.14}',
      '{"answer": 3.14}',
    ]);
    try {
      await expect(
        new NumberPrompt({ message: "x", floatAllowed: false }).execute(),
      ).rejects.toThrow("Decimal numbers are not allowed");
    } finally {
      restore();
    }
  });

  it("NumberPrompt truncates integer float when not allowed", async () => {
    const restore = setup([ACK, '{"answer": 5.0}']);
    try {
      const result = await new NumberPrompt({ message: "x", floatAllowed: false }).execute();
      expect(result).toBe(5);
      expect(Number.isInteger(result)).toBe(true);
    } finally {
      restore();
    }
  });

  it("NumberPrompt uses default on null", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(await new NumberPrompt({ message: "x", default: 42 }).execute()).toBe(42);
    } finally {
      restore();
    }
  });

  it("RawlistPrompt accepts by value", async () => {
    const restore = setup([ACK, '{"answer": "3.12"}']);
    try {
      const result = await new RawlistPrompt({
        message: "x",
        choices: ["3.13", "3.12"],
      }).execute();
      expect(result).toBe("3.12");
    } finally {
      restore();
    }
  });

  it("RawlistPrompt rejects invalid index", async () => {
    const restore = setup([
      ACK,
      '{"answer": 99}',
      '{"answer": 99}',
      '{"answer": 99}',
      '{"answer": 99}',
    ]);
    try {
      await expect(
        new RawlistPrompt({ message: "x", choices: ["a"] }).execute(),
      ).rejects.toThrow("Invalid choice");
    } finally {
      restore();
    }
  });

  it("ExpandPrompt rejects invalid key", async () => {
    const restore = setup([
      ACK,
      '{"answer": "z"}',
      '{"answer": "z"}',
      '{"answer": "z"}',
      '{"answer": "z"}',
    ]);
    try {
      await expect(
        new ExpandPrompt({
          message: "x",
          choices: [{ key: "y", name: "Yes", value: "yes" }],
        }).execute(),
      ).rejects.toThrow("Invalid choice");
    } finally {
      restore();
    }
  });

  it("ExpandPrompt detects duplicate keys", () => {
    expect(
      () =>
        new ExpandPrompt({
          message: "x",
          choices: [
            { key: "y", name: "A", value: "a" },
            { key: "y", name: "B", value: "b" },
          ],
        }),
    ).toThrow(InvalidChoiceError);
  });

  it("PathPrompt returns default on null", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(
        await new PathPrompt({ message: "x", default: "/tmp" }).execute(),
      ).toBe("/tmp");
    } finally {
      restore();
    }
  });

  it("AutocompletePrompt returns default on null", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(
        await new AutocompletePrompt({
          message: "x",
          choices: ["a"],
          default: "b",
        }).execute(),
      ).toBe("b");
    } finally {
      restore();
    }
  });

  it("PasswordPrompt returns default on null", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(await new PasswordPrompt({ message: "x" }).execute()).toBe("");
    } finally {
      restore();
    }
  });

  it("EditorPrompt returns default on null", async () => {
    const restore = setup([ACK, '{"answer": null}']);
    try {
      expect(
        await new EditorPrompt({ message: "x", default: "template" }).execute(),
      ).toBe("template");
    } finally {
      restore();
    }
  });

  it("filter function is applied", async () => {
    const restore = setup([ACK, '{"answer": "  hello  "}']);
    try {
      const result = await new TextPrompt({
        message: "x",
        filter: (s) => s.trim(),
      }).execute();
      expect(result).toBe("hello");
    } finally {
      restore();
    }
  });

  it("validate function rejects after retries", async () => {
    // User validation retries: 3 retries in execute() loop, so 4 answers needed
    // But executeAgent also re-sends the prompt each time, so we need 4 answers
    const restore = setup([
      ACK,
      '{"answer": "ab"}',
      '{"answer": "ab"}',
      '{"answer": "ab"}',
      '{"answer": "ab"}',
    ]);
    try {
      await expect(
        new TextPrompt({
          message: "x",
          validate: (s) => (s.length >= 3 ? true : "Too short"),
        }).execute(),
      ).rejects.toThrow(ValidationError);
    } finally {
      restore();
    }
  });

  it("validate function succeeds on retry", async () => {
    // First answer fails validation, second succeeds
    const restore = setup([
      ACK,
      '{"answer": "ab"}',
      '{"answer": "abc"}',
    ]);
    try {
      const result = await new TextPrompt({
        message: "x",
        validate: (s) => (s.length >= 3 ? true : "Too short"),
      }).execute();
      expect(result).toBe("abc");
    } finally {
      restore();
    }
  });
});
