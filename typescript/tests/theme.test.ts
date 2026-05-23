import { beforeEach, describe, expect, it } from "vitest";
import { ansi, BOLD, defaultTheme, getTheme, RESET, setTheme } from "../src/theme.js";

describe("Theme", () => {
  beforeEach(() => {
    setTheme(defaultTheme);
  });

  it("getTheme returns default theme", () => {
    const t = getTheme();
    expect(t.symQuestion).toBe("?");
    expect(t.symSuccess).toBe("✓");
    expect(t.symPointer).toBe("❯");
    expect(t.symChecked).toBe("◉");
    expect(t.symUnchecked).toBe("◯");
  });

  it("setTheme overrides specific fields", () => {
    setTheme({ symQuestion: "Q" });
    expect(getTheme().symQuestion).toBe("Q");
    expect(getTheme().symSuccess).toBe("✓");
  });

  it("ansi generates RGB escape code", () => {
    expect(ansi("#ff0000")).toBe("\x1b[38;2;255;0;0m");
    expect(ansi("#00ff00")).toBe("\x1b[38;2;0;255;0m");
  });

  it("RESET and BOLD are ANSI codes", () => {
    expect(RESET).toBe("\x1b[0m");
    expect(BOLD).toBe("\x1b[1m");
  });
});
