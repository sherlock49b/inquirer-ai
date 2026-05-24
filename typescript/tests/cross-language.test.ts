import * as fc from "fast-check";
import { describe, expect, it } from "vitest";
import { ValidationError } from "../src/errors.js";
import { ConfirmPrompt } from "../src/prompts/confirm.js";
import { NumberPrompt } from "../src/prompts/number.js";

/**
 * Cross-language consistency tests.
 *
 * These verify that TypeScript coerceBool / validateNumber behave the same
 * as the Python, Go, and Rust implementations where semantics should match.
 * Where TS intentionally diverges the test documents the difference.
 */

// Helper: call the private validateAnswer on ConfirmPrompt
function coerceBool(value: unknown): boolean {
  const prompt = new ConfirmPrompt({ message: "x" });
  return (prompt as any).validateAnswer(value);
}

// Helper: call the private validateAnswer on NumberPrompt with options
function validateNumber(
  value: unknown,
  opts: { min?: number; max?: number; floatAllowed?: boolean } = {},
): number {
  const prompt = new NumberPrompt({ message: "x", ...opts });
  return (prompt as any).validateAnswer(value);
}

// --------------------------------------------------------------------------
// coerceBool
// --------------------------------------------------------------------------
describe("Cross-language: coerceBool", () => {
  // -- Primitive booleans --------------------------------------------------
  it("true → true", () => {
    expect(coerceBool(true)).toBe(true);
  });

  it("false → false", () => {
    expect(coerceBool(false)).toBe(false);
  });

  // -- null / undefined ----------------------------------------------------
  it("null → false", () => {
    expect(coerceBool(null)).toBe(false);
  });

  it("undefined → false", () => {
    expect(coerceBool(undefined)).toBe(false);
  });

  // -- Numeric edge cases --------------------------------------------------
  it("0 → false", () => {
    expect(coerceBool(0)).toBe(false);
  });

  it("1 → true", () => {
    expect(coerceBool(1)).toBe(true);
  });

  it("-1 → true", () => {
    expect(coerceBool(-1)).toBe(true);
  });

  it("NaN → false (TS correct: Boolean(NaN) is false)", () => {
    expect(coerceBool(Number.NaN)).toBe(false);
  });

  it("Infinity → false (cross-lang: non-finite should be false)", () => {
    // Boolean(Infinity) is true in JS, but Python/Go/Rust treat non-finite
    // as false.  If TS wants cross-language consistency this should be false.
    expect(coerceBool(Number.POSITIVE_INFINITY)).toBe(false);
  });

  it("-Infinity → false (cross-lang: non-finite should be false)", () => {
    expect(coerceBool(Number.NEGATIVE_INFINITY)).toBe(false);
  });

  // -- String truthy values ------------------------------------------------
  it('"yes" → true', () => {
    expect(coerceBool("yes")).toBe(true);
  });

  it('"y" → true', () => {
    expect(coerceBool("y")).toBe(true);
  });

  it('"true" → true', () => {
    expect(coerceBool("true")).toBe(true);
  });

  it('"1" → true', () => {
    expect(coerceBool("1")).toBe(true);
  });

  // -- String falsy values -------------------------------------------------
  it('"no" → false', () => {
    expect(coerceBool("no")).toBe(false);
  });

  it('"n" → false', () => {
    expect(coerceBool("n")).toBe(false);
  });

  it('"false" → false', () => {
    expect(coerceBool("false")).toBe(false);
  });

  it('"0" → false', () => {
    expect(coerceBool("0")).toBe(false);
  });

  it('"" → false', () => {
    expect(coerceBool("")).toBe(false);
  });

  // -- Case insensitivity --------------------------------------------------
  it('"YES" → true (case insensitive)', () => {
    expect(coerceBool("YES")).toBe(true);
  });

  it('"True" → true (case insensitive)', () => {
    expect(coerceBool("True")).toBe(true);
  });

  it('"NO" → false (case insensitive)', () => {
    expect(coerceBool("NO")).toBe(false);
  });

  it('"FALSE" → false (case insensitive)', () => {
    expect(coerceBool("FALSE")).toBe(false);
  });
});

// --------------------------------------------------------------------------
// validateNumber
// --------------------------------------------------------------------------
describe("Cross-language: validateNumber", () => {
  // -- Non-finite values ---------------------------------------------------
  it("NaN → error", () => {
    expect(() => validateNumber(Number.NaN)).toThrow(ValidationError);
  });

  it("Infinity → error", () => {
    expect(() => validateNumber(Number.POSITIVE_INFINITY)).toThrow(ValidationError);
  });

  it("-Infinity → error", () => {
    expect(() => validateNumber(Number.NEGATIVE_INFINITY)).toThrow(ValidationError);
  });

  it('"NaN" string → error', () => {
    expect(() => validateNumber("NaN")).toThrow(ValidationError);
  });

  it('"Infinity" string → error', () => {
    expect(() => validateNumber("Infinity")).toThrow(ValidationError);
  });

  it('"-Infinity" string → error', () => {
    expect(() => validateNumber("-Infinity")).toThrow(ValidationError);
  });

  // -- Normal numbers ------------------------------------------------------
  it("42 → 42", () => {
    expect(validateNumber(42)).toBe(42);
  });

  it("-7 → -7", () => {
    expect(validateNumber(-7)).toBe(-7);
  });

  it("0 → 0", () => {
    expect(validateNumber(0)).toBe(0);
  });

  it("3.14 → 3.14", () => {
    expect(validateNumber(3.14)).toBeCloseTo(3.14);
  });

  it('"42" string → 42', () => {
    expect(validateNumber("42")).toBe(42);
  });

  it('"3.14" string → 3.14', () => {
    expect(validateNumber("3.14")).toBeCloseTo(3.14);
  });

  // -- Min/max bounds ------------------------------------------------------
  it("value below min → error", () => {
    expect(() => validateNumber(5, { min: 10 })).toThrow(ValidationError);
  });

  it("value above max → error", () => {
    expect(() => validateNumber(20, { max: 10 })).toThrow(ValidationError);
  });

  it("value at min boundary → ok", () => {
    expect(validateNumber(10, { min: 10 })).toBe(10);
  });

  it("value at max boundary → ok", () => {
    expect(validateNumber(10, { max: 10 })).toBe(10);
  });

  it("value within [min, max] → ok", () => {
    expect(validateNumber(5, { min: 0, max: 10 })).toBe(5);
  });

  // -- floatAllowed --------------------------------------------------------
  it("floatAllowed=false: 3.0 → ok (integer value)", () => {
    expect(validateNumber(3.0, { floatAllowed: false })).toBe(3);
  });

  it("floatAllowed=false: 3.5 → error", () => {
    expect(() => validateNumber(3.5, { floatAllowed: false })).toThrow(ValidationError);
  });

  it("floatAllowed=false: integer string → ok", () => {
    expect(validateNumber("7", { floatAllowed: false })).toBe(7);
  });

  // -- Type rejection ------------------------------------------------------
  it("boolean → error", () => {
    expect(() => validateNumber(true)).toThrow(ValidationError);
  });

  it("null without default → error", () => {
    expect(() => validateNumber(null)).toThrow(ValidationError);
  });
});

// --------------------------------------------------------------------------
// Property-based tests
// --------------------------------------------------------------------------
describe("Cross-language: property-based", () => {
  it("coerceBool always returns boolean type", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.boolean(),
          fc.string(),
          fc.integer(),
          fc.double(),
          fc.constant(null),
          fc.constant(undefined),
          fc.constant(Number.NaN),
          fc.constant(Number.POSITIVE_INFINITY),
          fc.constant(Number.NEGATIVE_INFINITY),
        ),
        (value) => {
          const result = coerceBool(value);
          expect(typeof result).toBe("boolean");
        },
      ),
    );
  });

  it("coerceBool is idempotent: coerceBool(coerceBool(x)) === coerceBool(x)", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.boolean(),
          fc.string(),
          fc.integer(),
          fc.constant(null),
          fc.constant(undefined),
        ),
        (value) => {
          const once = coerceBool(value);
          const twice = coerceBool(once);
          expect(twice).toBe(once);
        },
      ),
    );
  });

  it("validateNumber: valid result is within [min, max]", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: -10000, max: 10000 }),
        fc.integer({ min: -5000, max: 0 }),
        fc.integer({ min: 0, max: 5000 }),
        (value, minVal, maxVal) => {
          if (minVal > maxVal) return;
          try {
            const result = validateNumber(value, { min: minVal, max: maxVal });
            expect(result).toBeGreaterThanOrEqual(minVal);
            expect(result).toBeLessThanOrEqual(maxVal);
          } catch (e) {
            expect(e).toBeInstanceOf(ValidationError);
          }
        },
      ),
    );
  });

  it("validateNumber: result is always a finite number", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.integer(),
          fc.double({ noNaN: true, noDefaultInfinity: true }),
        ),
        (value) => {
          try {
            const result = validateNumber(value);
            expect(typeof result).toBe("number");
            expect(Number.isFinite(result)).toBe(true);
          } catch (e) {
            expect(e).toBeInstanceOf(ValidationError);
          }
        },
      ),
    );
  });
});
