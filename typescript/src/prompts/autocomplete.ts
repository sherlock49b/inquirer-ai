import { BasePrompt, type BaseConfig } from "./base.js";
import { formatQuestion, readLine } from "../terminal.js";

export interface AutocompleteConfig extends BaseConfig<string> {
  choices: string[];
}

export class AutocompletePrompt extends BasePrompt<string> {
  private choices: string[];

  constructor(config: AutocompleteConfig) {
    super(config);
    this.choices = config.choices;
  }

  get promptType(): string {
    return "autocomplete";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), choices: this.choices };
  }

  protected async executeTerminal(): Promise<string> {
    const suffix = this.defaultValue != null ? ` (${this.defaultValue})` : "";
    const prompt = formatQuestion(this.message, suffix);
    const result = await readLine(prompt);
    if (!result && this.defaultValue != null) return this.defaultValue;
    return result;
  }
}
