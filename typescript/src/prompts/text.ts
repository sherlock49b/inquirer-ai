import { formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface TextConfig extends BaseConfig<string> {
  default?: string | null;
  keepInput?: boolean;
}

export class TextPrompt extends BasePrompt<string> {
  private keepInput: boolean;
  private lastFailedInput: string | null = null;

  constructor(config: TextConfig) {
    super(config);
    this.keepInput = config.keepInput ?? true;
  }

  get promptType(): string {
    return "input";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected async executeTerminal(): Promise<string> {
    const effectiveDefault = this.lastFailedInput ?? this.defaultValue;
    const suffix = effectiveDefault != null ? ` (${effectiveDefault})` : "";
    const prompt = formatQuestion(this.message, suffix);
    const result = await readLine(prompt);
    const value = result || (effectiveDefault ?? "");
    if (this.keepInput && value) {
      this.lastFailedInput = value;
    }
    return value;
  }
}
