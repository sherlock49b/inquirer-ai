import { Readable, Writable } from "node:stream";
import { describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import {
  InvalidChoiceError,
  PromptAbortedError,
  ValidationError,
} from "../src/errors.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { SelectPrompt } from "../src/prompts/select.js";
import { TextPrompt } from "../src/prompts/text.js";

const ACK = '{"kind":"handshake_ack"}';

function setup(answers: string[]) {
  resetAgent();
  vi.stubEnv("INQUIRER_AI_MODE", "agent");
  const stdin = Readable.from(answers.map((a) => `${a}\n`).join(""));
  const writable = new Writable({
    write(_c: Buffer, _e: string, cb: () => void) {
      cb();
    },
  });
  const origStdin = process.stdin;
  const origStdout = process.stdout;
  Object.defineProperty(process, "stdin", {
    value: stdin,
    configurable: true,
  });
  Object.defineProperty(process, "stdout", {
    value: writable,
    configurable: true,
  });
  return () => {
    Object.defineProperty(process, "stdin", {
      value: origStdin,
      configurable: true,
    });
    Object.defineProperty(process, "stdout", {
      value: origStdout,
      configurable: true,
    });
  };
}

describe("Boundary tests", () => {
  describe("Validator throwing non-ValidationError exceptions", () => {
    it("validator throws TypeError — converted to ValidationError", async () => {
      const restore = setup([ACK, '{"answer": "test"}']);
      try {
        await expect(
          new TextPrompt({
            message: "x",
            validate: () => {
              throw new TypeError("Cannot read properties of undefined");
            },
          }).execute(),
        ).rejects.toSatisfy((err: Error) => {
          expect(err).toBeInstanceOf(ValidationError);
          expect(err.message).toBe(
            "Cannot read properties of undefined",
          );
          return true;
        });
      } finally {
        restore();
      }
    });

    it("validator throws generic Error — converted to ValidationError", async () => {
      const restore = setup([ACK, '{"answer": "test"}']);
      try {
        await expect(
          new TextPrompt({
            message: "x",
            validate: () => {
              throw new Error("something went wrong");
            },
          }).execute(),
        ).rejects.toSatisfy((err: Error) => {
          expect(err).toBeInstanceOf(ValidationError);
          expect(err.message).toBe("something went wrong");
          return true;
        });
      } finally {
        restore();
      }
    });
  });

  describe("Choice validation edge cases", () => {
    it("all choices disabled — throws InvalidChoiceError", () => {
      expect(
        () =>
          new SelectPrompt({
            message: "x",
            choices: [
              { name: "a", value: "a", disabled: true },
              { name: "b", value: "b", disabled: "not available" },
            ],
          }),
      ).toThrow(InvalidChoiceError);
    });

    it("empty choice list — throws InvalidChoiceError", () => {
      expect(
        () =>
          new SelectPrompt({
            message: "x",
            choices: [],
          }),
      ).toThrow(InvalidChoiceError);
    });

    it("checkbox with all choices disabled — throws InvalidChoiceError", () => {
      expect(
        () =>
          new CheckboxPrompt({
            message: "x",
            choices: [
              { name: "a", value: "a", disabled: true },
              { name: "b", value: "b", disabled: true },
            ],
          }),
      ).toThrow(InvalidChoiceError);
    });

    it("checkbox with empty choice list — throws InvalidChoiceError", () => {
      expect(
        () =>
          new CheckboxPrompt({
            message: "x",
            choices: [],
          }),
      ).toThrow(InvalidChoiceError);
    });
  });

  describe("stdin EOF in agent mode", () => {
    it("stdin EOF — throws PromptAbortedError", async () => {
      const restore = setup([]);
      try {
        await expect(
          new TextPrompt({ message: "x" }).execute(),
        ).rejects.toSatisfy((err: Error) => {
          expect(err).toBeInstanceOf(PromptAbortedError);
          expect(err.message).toContain("stdin closed");
          return true;
        });
      } finally {
        restore();
      }
    });
  });

  describe("Invalid FD environment variables", () => {
    it("INQUIRER_AI_FD_OUT with non-numeric value falls back to stdout", async () => {
      const restore = setup([ACK, '{"answer": "hello"}']);
      const stderrSpy = vi.spyOn(process.stderr, "write");
      vi.stubEnv("INQUIRER_AI_FD_OUT", "abc");
      try {
        const result = await new TextPrompt({ message: "x" }).execute();
        expect(result).toBe("hello");
        expect(stderrSpy).toHaveBeenCalledWith(
          expect.stringContaining("invalid INQUIRER_AI_FD_OUT"),
        );
      } finally {
        vi.unstubAllEnvs();
        stderrSpy.mockRestore();
        restore();
      }
    });

    it("INQUIRER_AI_FD_IN with non-numeric value falls back to stdin", async () => {
      resetAgent();
      vi.stubEnv("INQUIRER_AI_MODE", "agent");
      vi.stubEnv("INQUIRER_AI_FD_IN", "not_a_number");

      const stderrSpy = vi.spyOn(process.stderr, "write");
      const stdin = Readable.from([`${ACK}\n`, '{"answer": "world"}\n']);
      const writable = new Writable({
        write(_c: Buffer, _e: string, cb: () => void) {
          cb();
        },
      });

      const origStdin = process.stdin;
      const origStdout = process.stdout;
      Object.defineProperty(process, "stdin", {
        value: stdin,
        configurable: true,
      });
      Object.defineProperty(process, "stdout", {
        value: writable,
        configurable: true,
      });

      try {
        const result = await new TextPrompt({ message: "x" }).execute();
        expect(result).toBe("world");
        expect(stderrSpy).toHaveBeenCalledWith(
          expect.stringContaining("invalid INQUIRER_AI_FD_IN"),
        );
      } finally {
        Object.defineProperty(process, "stdin", {
          value: origStdin,
          configurable: true,
        });
        Object.defineProperty(process, "stdout", {
          value: origStdout,
          configurable: true,
        });
        vi.unstubAllEnvs();
        stderrSpy.mockRestore();
      }
    });
  });
});
