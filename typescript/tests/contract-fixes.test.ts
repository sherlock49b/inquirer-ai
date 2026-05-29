import { describe, expect, it } from "vitest";
import { ValidationError } from "../src/errors.js";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { RawlistPrompt } from "../src/prompts/rawlist.js";
import { SelectPrompt } from "../src/prompts/select.js";

// Access the protected validateAnswer for unit-level assertions.
type Validatable = { validateAnswer: (v: unknown) => unknown };
function va(p: unknown): (v: unknown) => unknown {
  return (v) => (p as unknown as Validatable).validateAnswer(v);
}

// ---------------------------------------------------------------------------
// R2 — numeric-string grammar (NumberPrompt)
// ---------------------------------------------------------------------------
describe("R2: number grammar", () => {
  const num = (opts = {}) => va(new NumberPrompt({ message: "x", ...opts }));

  it("accepts exponent strings", () => {
    expect(num()("1e3")).toBe(1000);
    expect(num()("1E-3")).toBeCloseTo(0.001);
  });

  it("trims ASCII whitespace", () => {
    expect(num()("  5  ")).toBe(5);
  });

  it("rejects 1_000, 3abc, 0x10, .5, 5., '', +", () => {
    for (const bad of ["1_000", "3abc", "0x10", ".5", "5.", "", "+"]) {
      expect(() => num()(bad)).toThrow(ValidationError);
    }
  });

  it("rejects booleans with a type error", () => {
    expect(() => num()(true)).toThrow("Expected a number, got boolean");
  });

  it("null + default present -> default", () => {
    expect(num({ default: 42 })(null)).toBe(42);
  });

  it("floatAllowed=false coerces an integral float to int", () => {
    expect(num({ floatAllowed: false })(5.0)).toBe(5);
    expect(() => num({ floatAllowed: false })(3.5)).toThrow("Decimal numbers are not allowed");
  });
});

// ---------------------------------------------------------------------------
// R4 — type-aware value matching (no JS cross-coercion)
// ---------------------------------------------------------------------------
describe("R4: type-aware matching", () => {
  it("select: string '42' does not match number 42 value", () => {
    const p = va(new SelectPrompt({ message: "x", choices: [{ name: "n", value: 42 }] }));
    expect(p(42)).toBe(42);
    expect(() => p("42")).toThrow(ValidationError);
  });

  it("select: 0 does not cross-match false; 1 does not cross-match true", () => {
    const p = va(new SelectPrompt({ message: "x", choices: [{ name: "zero", value: 0 }, { name: "yes", value: true }] }));
    expect(p(0)).toBe(0);
    expect(p(true)).toBe(true);
    // false is not a valid choice and must NOT match the 0 choice.
    expect(() => p(false)).toThrow(ValidationError);
    // 1 is not a valid choice and must NOT match the `true` choice.
    expect(() => p(1)).toThrow(ValidationError);
  });

  it("select: exact string-name match resolves to value", () => {
    const p = va(new SelectPrompt({ message: "x", choices: [{ name: "Go", value: "golang" }] }));
    expect(p("Go")).toBe("golang");
  });

  it("select: disabled choices never match", () => {
    const p = va(
      new SelectPrompt({
        message: "x",
        choices: [
          { name: "Go", value: "go", disabled: true },
          { name: "Rust", value: "rust" },
        ],
      }),
    );
    expect(() => p("go")).toThrow(ValidationError);
    expect(() => p("Go")).toThrow(ValidationError);
  });

  it("checkbox: numeric answer string-matching a name is resolved, not dropped", () => {
    // choice name "1" with a distinct value: a string answer "1" must resolve.
    const p = va(new CheckboxPrompt({ message: "x", choices: [{ name: "1", value: "one" }] }));
    expect(p(["1"])).toEqual(["one"]);
    // a numeric 1 must NOT match the string name "1" (no coercion) and rejects.
    expect(() => p([1])).toThrow(ValidationError);
  });

  it("checkbox: empty-string disabled is enabled (false-y disabled)", () => {
    const p = va(
      new CheckboxPrompt({
        message: "x",
        choices: [{ name: "A", value: "a", disabled: "" }],
      }),
    );
    expect(p(["a"])).toEqual(["a"]);
  });
});

// ---------------------------------------------------------------------------
// R5 — rawlist integer index over the selectable list
// ---------------------------------------------------------------------------
describe("R5: rawlist", () => {
  it("rejects a fractional index (1.5) rather than truncating", () => {
    const p = va(new RawlistPrompt({ message: "x", choices: ["a", "b", "c"] }));
    expect(() => p(1.5)).toThrow(ValidationError);
  });

  it("accepts a 1-based integer index", () => {
    const p = va(new RawlistPrompt({ message: "x", choices: ["a", "b", "c"] }));
    expect(p(2)).toBe("b");
  });

  it("indexes over the selectable list (skips disabled)", () => {
    const p = va(
      new RawlistPrompt({
        message: "x",
        choices: [
          { name: "A", value: "a", disabled: true },
          { name: "B", value: "b" },
          { name: "C", value: "c" },
        ],
      }),
    );
    // Index 1 is the first SELECTABLE choice (B), not the disabled A.
    expect(p(1)).toBe("b");
    expect(p(2)).toBe("c");
    expect(() => p(3)).toThrow(ValidationError);
    // The disabled choice's value must not match either.
    expect(() => p("a")).toThrow(ValidationError);
  });
});
