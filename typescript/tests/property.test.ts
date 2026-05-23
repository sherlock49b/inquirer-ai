import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { parseChoice, isSeparator, choiceToDict, createSeparator } from "../src/choice.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { ConfirmPrompt } from "../src/prompts/confirm.js";
import { ValidationError } from "../src/errors.js";

describe("Property-based tests", () => {
  it("Choice roundtrip: parseChoice(string) preserves name=value", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1 }), (s) => {
        const c = parseChoice(s);
        if (!isSeparator(c)) {
          expect(c.name).toBe(s);
          expect(c.value).toBe(s);
        }
      }),
    );
  });

  it("choiceToDict always produces valid dict", () => {
    fc.assert(
      fc.property(
        fc.record({
          name: fc.string({ minLength: 1 }),
          value: fc.string(),
          disabled: fc.oneof(fc.constant(false), fc.constant(true), fc.string()),
          short: fc.option(fc.string(), { nil: undefined }),
          description: fc.option(fc.string(), { nil: undefined }),
        }),
        (choice) => {
          const d = choiceToDict(choice);
          expect(d["name"]).toBe(choice.name);
          expect(d["value"]).toBe(choice.value);
        },
      ),
    );
  });

  it("Separator roundtrip", () => {
    fc.assert(
      fc.property(fc.string(), (text) => {
        const sep = createSeparator(text);
        const d = choiceToDict(sep);
        expect(d["type"]).toBe("separator");
        expect(d["text"]).toBe(text);
      }),
    );
  });

  it("NumberPrompt validateAnswer respects min/max bounds", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: -1000, max: 1000 }),
        fc.integer({ min: -500, max: 0 }),
        fc.integer({ min: 0, max: 500 }),
        (value, minVal, maxVal) => {
          if (minVal > maxVal) return;
          const prompt = new NumberPrompt({
            message: "x",
            min: minVal,
            max: maxVal,
          });
          try {
            const result = (prompt as any).validateAnswer(value);
            expect(result).toBeGreaterThanOrEqual(minVal);
            expect(result).toBeLessThanOrEqual(maxVal);
          } catch (e) {
            expect(e).toBeInstanceOf(ValidationError);
          }
        },
      ),
    );
  });

  it("ConfirmPrompt validateAnswer always returns boolean", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.boolean(), fc.string(), fc.integer()),
        (value) => {
          const prompt = new ConfirmPrompt({ message: "x" });
          const result = (prompt as any).validateAnswer(value);
          expect(typeof result).toBe("boolean");
        },
      ),
    );
  });

  it("NumberPrompt rejects non-finite values", () => {
    const prompt = new NumberPrompt({ message: "x" });
    for (const val of [NaN, Infinity, -Infinity, "NaN", "Infinity", "-Infinity"]) {
      expect(() => (prompt as any).validateAnswer(val)).toThrow(ValidationError);
    }
  });
});
