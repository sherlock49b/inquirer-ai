export interface Choice<V = unknown> {
  name: string;
  value: V;
  disabled?: boolean | string;
  short?: string;
  description?: string;
}

export interface Separator {
  type: "separator";
  text: string;
}

export type ChoiceItem<V = unknown> = Choice<V> | Separator;
export type RawChoice<V = unknown> = string | Choice<V> | Separator;

export function isSeparator(item: ChoiceItem): item is Separator {
  return "type" in item && item.type === "separator";
}

/**
 * Type-aware value matching (R4). An answer matches a choice's value only if it
 * has the same JSON type and value. JS strict equality already refuses to
 * cross-match types (`"42" !== 42`, `true !== 1`, `0 !== false`), so we never
 * string-coerce. Arrays/objects are compared structurally via canonical JSON.
 */
export function valuesMatch(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  // Distinguish primitives strictly: only fall back to structural comparison
  // when both sides are non-null objects of the same kind.
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) {
    return false;
  }
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

/**
 * Build the canonical "Invalid choice" validation message shared across the
 * select / checkbox / rawlist / expand prompts. The rejected answer and each
 * valid option are encoded as compact JSON, and the valid options are joined by
 * ", " (comma + single space). This string is byte-identical across all four
 * language implementations (conformance parity), e.g.
 *   Invalid choice: "rs". Valid: ["py", "go"]
 *   Invalid choice: 1.5. Valid: ["313", "311"]
 */
export function invalidChoiceMessage(answer: unknown, validValues: unknown[]): string {
  const valid = validValues.map((v) => JSON.stringify(v)).join(", ");
  return `Invalid choice: ${JSON.stringify(answer)}. Valid: [${valid}]`;
}

export function createSeparator(text = "────────"): Separator {
  return { type: "separator", text };
}

export function parseChoice<V = unknown>(raw: RawChoice<V>): ChoiceItem<V> {
  if (typeof raw === "string") {
    // When a raw string is passed, it serves as both name and value.
    // The caller is responsible for ensuring V is compatible with string
    // (e.g., RawChoice<string> or RawChoice<unknown>).
    return { name: raw, value: raw as V };
  }
  if ("type" in raw && raw.type === "separator") {
    return raw;
  }
  // A choice with a missing value defaults its value to its name (R4).
  if (!("value" in raw) || (raw as Choice<V>).value === undefined) {
    return { ...(raw as Choice<V>), value: (raw as Choice<V>).name as unknown as V };
  }
  return raw;
}

export function choiceToDict(item: ChoiceItem): Record<string, unknown> {
  if (isSeparator(item)) {
    return { type: "separator", text: item.text };
  }
  const d: Record<string, unknown> = { name: item.name, value: item.value };
  if (item.disabled) d.disabled = item.disabled;
  if (item.short != null) d.short = item.short;
  if (item.description != null) d.description = item.description;
  return d;
}
