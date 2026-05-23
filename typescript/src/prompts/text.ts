import { BasePrompt, type BaseConfig } from "./base.js";
import { formatQuestion, readLine } from "../terminal.js";

export interface TextConfig extends BaseConfig<string> {
  default?: string | null;
}

export class TextPrompt extends BasePrompt<string> {
  constructor(config: TextConfig) {
    super(config);
  }

  get promptType(): string {
    return "input";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected async executeTerminal(): Promise<string> {
    const suffix = this.defaultValue != null ? ` (${this.defaultValue})` : "";
    const prompt = formatQuestion(this.message, suffix);
    const result = await readLine(prompt);
    if (!result && this.defaultValue != null) return this.defaultValue;
    return result;
  }
}
