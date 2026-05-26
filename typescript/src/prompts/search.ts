import { agentReceive, agentSend, agentSendValidationError } from "../agent.js";
import { type Choice, choiceToDict, isSeparator, parseChoice, type RawChoice } from "../choice.js";
import { PromptAbortedError, ValidationError } from "../errors.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface SearchConfig extends BaseConfig<unknown> {
  source: (term: string) => RawChoice[] | Promise<RawChoice[]>;
  pageSize?: number;
}

const MAX_AGENT_RETRIES = 3;

export class SearchPrompt extends BasePrompt<unknown> {
  private source: (term: string) => RawChoice[] | Promise<RawChoice[]>;
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

  private async callSource(term: string): Promise<Choice[]> {
    const result = this.source(term);
    const raw = result instanceof Promise ? await result : result;
    return raw
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
  }

  protected override toAgentDict(): Record<string, unknown> {
    // For sync sources, include initial choices; for async sources,
    // the choices are populated in executeAgent instead.
    const result = this.source("");
    if (result instanceof Promise) {
      return {
        ...super.toAgentDict(),
        searchable: true,
        choices: [],
      };
    }
    const initial = result
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
    return {
      ...super.toAgentDict(),
      searchable: true,
      choices: initial.map(choiceToDict),
    };
  }

  private async toAgentDictAsync(): Promise<Record<string, unknown>> {
    const initial = await this.callSource("");
    return {
      ...super.toAgentDict(),
      searchable: true,
      choices: initial.map(choiceToDict),
    };
  }

  protected override async executeAgent(): Promise<unknown> {
    const dict = await this.toAgentDictAsync();
    for (let attempt = 0; attempt <= MAX_AGENT_RETRIES; attempt++) {
      await agentSend(dict);
      let answer: unknown;
      try {
        answer = await agentReceive();
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("stdin closed")) throw new PromptAbortedError(msg);
        throw new ValidationError(msg);
      }
      try {
        return this.validateAnswer(answer);
      } catch (err) {
        if (err instanceof ValidationError && attempt < MAX_AGENT_RETRIES) {
          agentSendValidationError(err.message);
          continue;
        }
        throw err;
      }
    }
    throw new ValidationError("Maximum validation retries exceeded");
  }

  protected async executeTerminal(): Promise<unknown> {
    const t = getTheme();
    const filtered = await this.callSource("");
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
          if (filtered.length) return { done: true, result: filtered[cursor]?.value };
          return { done: true, result: null };
        }
        if (key === "ctrl-c") return { done: true, result: null };
        return { done: false };
      },
    });

    if (raw === null) throw new PromptAbortedError("Prompt aborted by user");
    return raw;
  }
}
