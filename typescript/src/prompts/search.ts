import { type Choice, type RawChoice, parseChoice, isSeparator, choiceToDict } from "../choice.js";
import { PromptAbortedError } from "../errors.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { BasePrompt, type BaseConfig } from "./base.js";

export interface SearchConfig extends BaseConfig<unknown> {
  source: (term: string) => RawChoice[];
  pageSize?: number;
}

export class SearchPrompt extends BasePrompt<unknown> {
  private source: (term: string) => RawChoice[];
  private pageSize: number;

  constructor(config: SearchConfig) {
    super(config);
    this.source = config.source;
    this.pageSize = config.pageSize ?? 10;
  }

  get promptType(): string {
    return "search";
  }

  protected validateAnswer(value: unknown): unknown {
    return value;
  }

  protected override toAgentDict(): Record<string, unknown> {
    const initial = this.source("")
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
    return {
      ...super.toAgentDict(),
      searchable: true,
      choices: initial.map(choiceToDict),
    };
  }

  protected async executeTerminal(): Promise<unknown> {
    const t = getTheme();
    let filtered = this.getFiltered("");
    let cursor = 0;

    const getItems = (): ListItem[] => {
      const end = Math.min(filtered.length, this.pageSize);
      const result: ListItem[] = [];
      for (let i = 0; i < end; i++) {
        const c = filtered[i]!;
        if (i === cursor) {
          result.push({ text: `${t.symPointer} ${c.name}`, style: ansi(t.highlight) });
        } else {
          result.push({ text: `  ${c.name}`, style: "" });
        }
      }
      if (!filtered.length) {
        result.push({ text: `  ${ansi(t.muted)}No matches${RESET}`, style: "" });
      }
      return result;
    };

    const raw = await runListPrompt({
      message: this.message,
      getItems,
      onKey: (key) => {
        if (key === "up") {
          if (filtered.length) cursor = (cursor - 1 + filtered.length) % filtered.length;
          return { done: false };
        }
        if (key === "down") {
          if (filtered.length) cursor = (cursor + 1) % filtered.length;
          return { done: false };
        }
        if (key === "enter") {
          if (filtered.length) return { done: true, result: filtered[cursor]!.value };
          return { done: true, result: null };
        }
        if (key === "ctrl-c") return { done: true, result: null };
        return { done: false };
      },
    });

    if (raw === null) throw new PromptAbortedError("Prompt aborted by user");
    return raw;
  }

  private getFiltered(term: string): Choice[] {
    return this.source(term)
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
  }
}
