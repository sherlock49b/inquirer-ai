import { describe, expect, it } from "vitest";
import { choiceToDict, createSeparator, isSeparator, parseChoice } from "../src/choice.js";

describe("Choice", () => {
  it("parseChoice from string", () => {
    const choice = parseChoice("hello");
    expect(isSeparator(choice)).toBe(false);
    if (!isSeparator(choice)) {
      expect(choice.name).toBe("hello");
      expect(choice.value).toBe("hello");
    }
  });

  it("parseChoice from Choice object", () => {
    const choice = parseChoice({ name: "Go", value: "go", description: "Systems language" });
    if (!isSeparator(choice)) {
      expect(choice.name).toBe("Go");
      expect(choice.value).toBe("go");
      expect(choice.description).toBe("Systems language");
    }
  });

  it("parseChoice from Separator", () => {
    const sep = createSeparator("---");
    const parsed = parseChoice(sep);
    expect(isSeparator(parsed)).toBe(true);
    if (isSeparator(parsed)) {
      expect(parsed.text).toBe("---");
    }
  });

  it("createSeparator defaults", () => {
    const sep = createSeparator();
    expect(sep.type).toBe("separator");
    expect(sep.text).toBe("────────");
  });

  it("choiceToDict includes optional fields", () => {
    const d = choiceToDict({
      name: "A",
      value: "a",
      disabled: "coming soon",
      short: "a",
      description: "desc",
    });
    expect(d).toEqual({
      name: "A",
      value: "a",
      disabled: "coming soon",
      short: "a",
      description: "desc",
    });
  });

  it("choiceToDict omits optional fields when absent", () => {
    const d = choiceToDict({ name: "A", value: "a" });
    expect(d).toEqual({ name: "A", value: "a" });
    expect("disabled" in d).toBe(false);
    expect("short" in d).toBe(false);
    expect("description" in d).toBe(false);
  });

  it("choiceToDict for separator", () => {
    const d = choiceToDict(createSeparator("==="));
    expect(d).toEqual({ type: "separator", text: "===" });
  });
});
