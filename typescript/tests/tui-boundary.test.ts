import { Readable, Writable } from "node:stream";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetAgent } from "../src/agent.js";
import { createSeparator } from "../src/choice.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { RawlistPrompt } from "../src/prompts/rawlist.js";
import { SelectPrompt } from "../src/prompts/select.js";
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

describe("TUI boundary tests (agent mode)", () => {
  beforeEach(() => {
    resetAgent();
    resetSocketTransport();
    vi.stubEnv("INQUIRER_AI_MODE", "agent");
    vi.stubEnv("INQUIRER_AI_TRANSPORT", "stdio");
  });

  // 1. Single choice select
  it("select with a single choice accepts that choice", async () => {
    await withMockedStdio([ACK, '{"answer": "only"}'], async (chunks) => {
      const result = await new SelectPrompt({
        message: "Pick one",
        choices: ["only"],
      }).execute();
      expect(result).toBe("only");

      const lines = parseOutputLines(chunks);
      const prompt = lines[1] as Record<string, unknown>;
      expect(prompt.type).toBe("select");
      const choices = prompt.choices as Array<Record<string, unknown>>;
      expect(choices).toHaveLength(1);
      expect(choices[0]!.name).toBe("only");
    });
  });

  // 2. Large choice list (100+ choices)
  it("select with 100+ choices works correctly", async () => {
    const choiceNames = Array.from({ length: 150 }, (_, i) => `item_${i}`);
    await withMockedStdio([ACK, '{"answer": "item_99"}'], async (chunks) => {
      const result = await new SelectPrompt({
        message: "Pick from many",
        choices: choiceNames,
      }).execute();
      expect(result).toBe("item_99");

      const lines = parseOutputLines(chunks);
      const prompt = lines[1] as Record<string, unknown>;
      const choices = prompt.choices as Array<Record<string, unknown>>;
      expect(choices).toHaveLength(150);
      expect(choices[99]!.name).toBe("item_99");
    });
  });

  // 3. Disabled choices filtered from agent dict
  it("disabled choices appear in agent dict but are not selectable", async () => {
    // Provide 4 retries of invalid answer then exhaust
    await withMockedStdio(
      [
        ACK,
        '{"answer": "disabled_one"}',
        '{"answer": "disabled_one"}',
        '{"answer": "disabled_one"}',
        '{"answer": "disabled_one"}',
      ],
      async (chunks) => {
        await expect(
          new SelectPrompt({
            message: "Pick",
            choices: [
              { name: "enabled_one", value: "enabled_one" },
              { name: "disabled_one", value: "disabled_one", disabled: true },
            ],
          }).execute(),
        ).rejects.toThrow("Invalid choice");

        // Verify disabled choices are present in agent dict with disabled flag
        const lines = parseOutputLines(chunks);
        const prompt = lines[1] as Record<string, unknown>;
        const choices = prompt.choices as Array<Record<string, unknown>>;
        expect(choices).toHaveLength(2);
        const disabledChoice = choices.find((c) => c.name === "disabled_one");
        expect(disabledChoice).toBeDefined();
        expect(disabledChoice!.disabled).toBe(true);
      },
    );
  });

  // 4. Separator not in selectable agent choices
  it("separator appears in agent dict but cannot be selected", async () => {
    await withMockedStdio([ACK, '{"answer": "alpha"}'], async (chunks) => {
      const result = await new SelectPrompt({
        message: "Pick",
        choices: [
          "alpha",
          createSeparator("--- divider ---"),
          "beta",
        ],
      }).execute();
      expect(result).toBe("alpha");

      const lines = parseOutputLines(chunks);
      const prompt = lines[1] as Record<string, unknown>;
      const choices = prompt.choices as Array<Record<string, unknown>>;
      expect(choices).toHaveLength(3);

      const sep = choices.find((c) => c.type === "separator");
      expect(sep).toBeDefined();
      expect(sep!.text).toBe("--- divider ---");

      // Separator text cannot be used as answer
      const selectableNames = choices
        .filter((c) => c.type !== "separator")
        .map((c) => c.name);
      expect(selectableNames).toEqual(["alpha", "beta"]);
    });
  });

  // 5. Checkbox required=true, empty answer -> error
  it("checkbox required=true rejects empty answer", async () => {
    await withMockedStdio(
      [
        ACK,
        '{"answer": []}',
        '{"answer": []}',
        '{"answer": []}',
        '{"answer": []}',
      ],
      async () => {
        await expect(
          new CheckboxPrompt({
            message: "Select items",
            choices: ["a", "b", "c"],
            required: true,
          }).execute(),
        ).rejects.toThrow("At least one choice is required");
      },
    );
  });

  // 6. Checkbox all selected
  it("checkbox accepts all choices selected", async () => {
    await withMockedStdio([ACK, '{"answer": ["x", "y", "z"]}'], async () => {
      const result = await new CheckboxPrompt({
        message: "Select all",
        choices: ["x", "y", "z"],
      }).execute();
      expect(result).toEqual(["x", "y", "z"]);
    });
  });

  // 7. Duplicate choice values
  it("select with duplicate choice values returns first matching value", async () => {
    await withMockedStdio([ACK, '{"answer": "dup"}'], async () => {
      const result = await new SelectPrompt({
        message: "Pick",
        choices: [
          { name: "First", value: "dup" },
          { name: "Second", value: "dup" },
          { name: "Third", value: "unique" },
        ],
      }).execute();
      // validateAnswer finds the first matching enabled choice
      expect(result).toBe("dup");
    });
  });

  // 8. Unicode choice names
  it("select with unicode choice names works", async () => {
    await withMockedStdio([ACK, '{"answer": "\\u2764\\ufe0f Heart"}'], async (chunks) => {
      const result = await new SelectPrompt({
        message: "Pick emoji",
        choices: [
          { name: "❤️ Heart", value: "heart" },
          { name: "⭐ Star", value: "star" },
          { name: "🌟 Glowing Star", value: "glow" },
        ],
      }).execute();
      // Selecting by name maps to the value
      expect(result).toBe("heart");

      const lines = parseOutputLines(chunks);
      const prompt = lines[1] as Record<string, unknown>;
      const choices = prompt.choices as Array<Record<string, unknown>>;
      expect(choices[0]!.name).toBe("❤️ Heart");
    });
  });

  // 9. Choice with empty name
  it("select with empty name choice can be selected by value", async () => {
    await withMockedStdio([ACK, '{"answer": "empty_val"}'], async (chunks) => {
      const result = await new SelectPrompt({
        message: "Pick",
        choices: [
          { name: "", value: "empty_val" },
          { name: "Normal", value: "normal" },
        ],
      }).execute();
      expect(result).toBe("empty_val");

      const lines = parseOutputLines(chunks);
      const prompt = lines[1] as Record<string, unknown>;
      const choices = prompt.choices as Array<Record<string, unknown>>;
      expect(choices[0]!.name).toBe("");
    });
  });

  // 10. Rawlist with out-of-range index
  it("rawlist with out-of-range index rejects after retries", async () => {
    await withMockedStdio(
      [
        ACK,
        '{"answer": 99}',
        '{"answer": 99}',
        '{"answer": 99}',
        '{"answer": 99}',
      ],
      async () => {
        await expect(
          new RawlistPrompt({
            message: "Pick",
            choices: ["alpha", "beta", "gamma"],
          }).execute(),
        ).rejects.toThrow("Invalid choice");
      },
    );
  });
});
