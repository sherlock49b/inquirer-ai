import { InvalidChoiceError, ValidationError } from "../errors.js";
import { formatError, formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface ExpandChoice {
  key: string;
  name: string;
  value: unknown;
}

export interface ExpandConfig extends BaseConfig<unknown> {
  choices: (ExpandChoice | Record<string, unknown>)[];
}

function parseExpandChoice(raw: ExpandChoice | Record<string, unknown>): ExpandChoice {
  if ("key" in raw && typeof raw.key === "string") {
    return {
      key: raw.key.toLowerCase(),
      name: (raw.name as string | undefined) ?? raw.key,
      value: raw.value ?? raw.key,
    };
  }
  throw new InvalidChoiceError("ExpandChoice must have a 'key' field");
}

export class ExpandPrompt extends BasePrompt<unknown> {
  private expandChoices: ExpandChoice[];

  constructor(config: ExpandConfig) {
    super(config);
    if (!config.choices.length) throw new InvalidChoiceError("choices cannot be empty");
    this.expandChoices = config.choices.map(parseExpandChoice);
    const keys = this.expandChoices.map((c) => c.key);
    const dupes = keys.filter((k, i) => keys.indexOf(k) !== i);
    if (dupes.length) throw new InvalidChoiceError(`Duplicate expand keys: ${[...new Set(dupes)]}`);
  }

  get promptType(): string {
    return "expand";
  }

  protected validateAnswer(value: unknown): unknown {
    if (typeof value === "string") {
      const lower = value.toLowerCase();
      for (const c of this.expandChoices) {
        if (lower === c.key || value === c.value || value === c.name) return c.value;
      }
    }
    throw new ValidationError(`Invalid choice: ${JSON.stringify(value)}`);
  }

  protected formatAnswer(value: unknown): string {
    for (const c of this.expandChoices) {
      if (c.value === value) return c.name;
    }
    return String(value);
  }

  protected override toAgentDict(): Record<string, unknown> {
    return {
      ...super.toAgentDict(),
      choices: this.expandChoices.map((c) => ({ key: c.key, name: c.name, value: c.value })),
    };
  }

  protected async executeTerminal(): Promise<unknown> {
    const keys = this.expandChoices.map((c) => c.key).join("/");
    const prompt = formatQuestion(this.message, ` (${keys})`);
    while (true) {
      const raw = await readLine(prompt);
      const lower = raw.trim().toLowerCase();
      if (lower === "h" || lower === "help") {
        for (const c of this.expandChoices) {
          process.stderr.write(`  ${c.key}) ${c.name}\n`);
        }
        continue;
      }
      for (const c of this.expandChoices) {
        if (lower === c.key) return c.value;
      }
      process.stderr.write(`${formatError("Invalid key. Press h for help.")}\n`);
    }
  }
}
