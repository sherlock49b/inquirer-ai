import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CheckboxPrompt } from "../src/prompts/checkbox.js";
import { ConfirmPrompt } from "../src/prompts/confirm.js";
import { NumberPrompt } from "../src/prompts/number.js";
import { SelectPrompt } from "../src/prompts/select.js";
import { TextPrompt } from "../src/prompts/text.js";
import { renderPrompt, } from "./helpers/tui.js";

beforeEach(() => {
  vi.stubEnv("INQUIRER_AI_MODE", "human");
  vi.stubEnv("INQUIRER_AI_TRANSPORT", "");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

/* ================================================================== */
/*  TextPrompt                                                         */
/* ================================================================== */

describe("TextPrompt terminal mode", () => {
  it("accepts typed input + enter", async () => {
    const t = renderPrompt<string>(() =>
      new TextPrompt({ message: "Name?" }).execute(),
    );
    // Small delay to let readline attach
    await tick();
    t.events.type("hello");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("hello");
    t.close();
  });

  it("returns default value on bare enter", async () => {
    const t = renderPrompt<string>(() =>
      new TextPrompt({ message: "Name?", default: "world" }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("world");
    t.close();
  });

  it("returns empty string when no default and bare enter", async () => {
    const t = renderPrompt<string>(() =>
      new TextPrompt({ message: "Name?" }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("");
    t.close();
  });
});

/* ================================================================== */
/*  ConfirmPrompt                                                      */
/* ================================================================== */

describe("ConfirmPrompt terminal mode", () => {
  it("y + enter returns true", async () => {
    const t = renderPrompt<boolean>(() =>
      new ConfirmPrompt({ message: "Continue?" }).execute(),
    );
    await tick();
    t.events.type("y");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe(true);
    t.close();
  });

  it("n + enter returns false", async () => {
    const t = renderPrompt<boolean>(() =>
      new ConfirmPrompt({ message: "Continue?" }).execute(),
    );
    await tick();
    t.events.type("n");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe(false);
    t.close();
  });

  it("bare enter returns default (false)", async () => {
    const t = renderPrompt<boolean>(() =>
      new ConfirmPrompt({ message: "Continue?" }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe(false);
    t.close();
  });

  it("bare enter returns default (true) when default is true", async () => {
    const t = renderPrompt<boolean>(() =>
      new ConfirmPrompt({ message: "Continue?", default: true }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe(true);
    t.close();
  });
});

/* ================================================================== */
/*  NumberPrompt                                                       */
/* ================================================================== */

describe("NumberPrompt terminal mode", () => {
  it("accepts a number", async () => {
    const t = renderPrompt<number>(() =>
      new NumberPrompt({ message: "Age?" }).execute(),
    );
    await tick();
    t.events.type("42");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe(42);
    t.close();
  });

  it("accepts a float", async () => {
    const t = renderPrompt<number>(() =>
      new NumberPrompt({ message: "Price?" }).execute(),
    );
    await tick();
    t.events.type("3.14");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBeCloseTo(3.14);
    t.close();
  });
});

/* ================================================================== */
/*  SelectPrompt                                                       */
/* ================================================================== */

describe("SelectPrompt terminal mode", () => {
  it("selects 3rd item with down+down+enter", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Pick one",
        choices: ["alpha", "beta", "gamma"],
      }).execute(),
    );
    await tick();
    t.events.keypress("down");
    t.events.keypress("down");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("gamma");
    t.close();
  });

  it("selects 1st item with enter (no navigation)", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Pick one",
        choices: ["alpha", "beta", "gamma"],
      }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("alpha");
    t.close();
  });

  it("digit jump: pressing 2 moves to 2nd item", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Pick one",
        choices: ["alpha", "beta", "gamma"],
      }).execute(),
    );
    await tick();
    t.events.keypress("2");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("beta");
    t.close();
  });

  it("loops around when pressing up from first item", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Pick one",
        choices: ["alpha", "beta", "gamma"],
        loop: true,
      }).execute(),
    );
    await tick();
    t.events.keypress("up");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toBe("gamma");
    t.close();
  });
});

/* ================================================================== */
/*  CheckboxPrompt                                                     */
/* ================================================================== */

describe("CheckboxPrompt terminal mode", () => {
  it("toggles items with space, submits with enter", async () => {
    const t = renderPrompt<string[]>(() =>
      new CheckboxPrompt({
        message: "Select items",
        choices: ["apple", "banana", "cherry"],
      }).execute(),
    );
    await tick();
    // Select first item
    t.events.keypress("space");
    // Move down, select second
    t.events.keypress("down");
    t.events.keypress("space");
    // Submit
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toEqual(["apple", "banana"]);
    t.close();
  });

  it("submits empty array when nothing selected", async () => {
    const t = renderPrompt<string[]>(() =>
      new CheckboxPrompt({
        message: "Select items",
        choices: ["apple", "banana"],
      }).execute(),
    );
    await tick();
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toEqual([]);
    t.close();
  });

  it("toggle all with 'a'", async () => {
    const t = renderPrompt<string[]>(() =>
      new CheckboxPrompt({
        message: "Select items",
        choices: ["apple", "banana", "cherry"],
      }).execute(),
    );
    await tick();
    // 'a' toggles all on
    t.events.keypress("a");
    t.events.keypress("enter");
    const result = await t.answer;
    expect(result).toEqual(["apple", "banana", "cherry"]);
    t.close();
  });
});

/* ================================================================== */
/*  Screen rendering assertions                                        */
/* ================================================================== */

describe("Screen rendering", () => {
  it("getScreen() shows question text for SelectPrompt", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Favorite color",
        choices: ["red", "green", "blue"],
      }).execute(),
    );
    await tick();
    const screen = t.getScreen();
    expect(screen).toContain("Favorite color");
    expect(screen).toContain("red");
    expect(screen).toContain("green");
    expect(screen).toContain("blue");
    // Clean up by selecting something
    t.events.keypress("enter");
    await t.answer;
    t.close();
  });

  it("getScreen() shows question text for TextPrompt", async () => {
    const t = renderPrompt<string>(() =>
      new TextPrompt({ message: "Your name" }).execute(),
    );
    await tick();
    const screen = t.getScreen();
    expect(screen).toContain("Your name");
    // Finish
    t.events.type("x");
    t.events.keypress("enter");
    await t.answer;
    t.close();
  });

  it("getScreen() shows Y/n hint for ConfirmPrompt", async () => {
    const t = renderPrompt<boolean>(() =>
      new ConfirmPrompt({ message: "Proceed?", default: true }).execute(),
    );
    await tick();
    const screen = t.getScreen();
    expect(screen).toContain("Proceed?");
    expect(screen).toContain("Y/n");
    // Finish
    t.events.keypress("enter");
    await t.answer;
    t.close();
  });

  it("getScreen() shows pointer symbol on current item in SelectPrompt", async () => {
    const t = renderPrompt<string>(() =>
      new SelectPrompt({
        message: "Pick",
        choices: ["aaa", "bbb", "ccc"],
      }).execute(),
    );
    await tick();
    const screen = t.getScreen();
    // The first item should have a pointer
    // The default theme uses "❯" as pointer
    expect(screen).toContain("❯");
    expect(screen).toContain("aaa");
    // Finish
    t.events.keypress("enter");
    await t.answer;
    t.close();
  });
});

/* ------------------------------------------------------------------ */
/*  Utility                                                            */
/* ------------------------------------------------------------------ */

/** Yield to the event loop so async prompt setup can complete. */
function tick(ms = 20): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
