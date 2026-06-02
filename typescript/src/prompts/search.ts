import { type Choice, choiceToDict, isSeparator, parseChoice, type RawChoice, valuesMatch } from "../choice.js";
import { PromptAbortedError } from "../errors.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface SearchConfig extends BaseConfig<unknown> {
  source: (term: string) => RawChoice[] | Promise<RawChoice[]>;
  pageSize?: number;
}

export class SearchPrompt extends BasePrompt<unknown> {
  private source: (term: string) => RawChoice[] | Promise<RawChoice[]>;
  private pageSize: number;
  // Choices advertised in the agent/socket payload, used to resolve answers (R5).
  private advertisedChoices: Choice[] = [];

  constructor(config: SearchConfig) {
    super(config);
    this.source = config.source;
    this.pageSize = config.pageSize ?? 10;
  }

  get promptType(): string {
    return "search";
  }

  protected validateAnswer(value: unknown): unknown {
    // If the answer matches an advertised choice (type-aware value match OR
    // exact name match) return that choice's value; otherwise return the answer
    // verbatim — this keeps dynamic search sources safe (R5).
    if (typeof value === "string") {
      for (const c of this.advertisedChoices) {
        if (value === c.name) return c.value;
      }
    }
    for (const c of this.advertisedChoices) {
      if (valuesMatch(value, c.value)) return c.value;
    }
    return value;
  }

  private async callSource(term: string): Promise<Choice[]> {
    const result = this.source(term);
    const raw = result instanceof Promise ? await result : result;
    return raw
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
  }

  protected override async buildAgentDict(): Promise<Record<string, unknown>> {
    // Resolve the initial choices (sync OR async source) so both the stdio and
    // socket transports advertise the resolved set, never an empty array (R6).
    const initial = await this.callSource("");
    this.advertisedChoices = initial;
    return {
      ...super.toAgentDict(),
      searchable: true,
      choices: initial.map(choiceToDict),
    };
  }

  protected async executeTerminal(): Promise<unknown> {
    const t = getTheme();
    let filtered = await this.callSource("");
    let cursor = 0;
    let searchTerm = "";
    let searching = false;
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    const refreshSource = (): void => {
      if (debounceTimer) clearTimeout(debounceTimer);
      searching = true;
      debounceTimer = setTimeout(() => {
        const result = this.source(searchTerm);
        const resolve = (raw: RawChoice[]): void => {
          filtered = raw
            .map(parseChoice)
            .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
          cursor = 0;
          searching = false;
        };
        if (result instanceof Promise) {
          result.then(resolve);
        } else {
          resolve(result);
        }
      }, 150);
    };

    const getItems = (): ListItem[] => {
      const items: ListItem[] = [];
      items.push({ text: `  ${ansi(t.muted)}Search: ${RESET}${searchTerm}`, style: "" });
      if (searching) {
        items.push({ text: `  ${ansi(t.muted)}Searching...${RESET}`, style: "" });
        return items;
      }
      const end = Math.min(filtered.length, this.pageSize);
      for (let i = 0; i < end; i++) {
        const c = filtered[i]!;
        if (i === cursor) {
          items.push({ text: `${t.symPointer} ${c.name}`, style: ansi(t.highlight) });
        } else {
          items.push({ text: `  ${c.name}`, style: "" });
        }
      }
      if (!filtered.length && !searching) {
        items.push({ text: `  ${ansi(t.muted)}No matches${RESET}`, style: "" });
      }
      return items;
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
          if (debounceTimer) clearTimeout(debounceTimer);
          if (filtered.length) return { done: true, result: filtered[cursor]?.value };
          return { done: true, result: null };
        }
        if (key === "ctrl-c") {
          if (debounceTimer) clearTimeout(debounceTimer);
          return { done: true, result: null };
        }
        if (key === "backspace") {
          if (searchTerm.length > 0) {
            searchTerm = searchTerm.slice(0, -1);
            refreshSource();
          }
          return { done: false };
        }
        if (key.length === 1 && key >= " ") {
          searchTerm += key;
          refreshSource();
          return { done: false };
        }
        return { done: false };
      },
    });

    if (raw === null) throw new PromptAbortedError("Prompt aborted by user");
    return raw;
  }
}
