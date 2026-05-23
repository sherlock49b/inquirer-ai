import { BasePrompt, type BaseConfig } from "./base.js";
import { formatQuestion, readPassword } from "../terminal.js";

export interface PasswordConfig extends BaseConfig<string> {
  mask?: string | null;
}

export class PasswordPrompt extends BasePrompt<string> {
  private mask: string | null;

  constructor(config: PasswordConfig) {
    super(config);
    this.mask = config.mask === undefined ? "*" : config.mask;
  }

  get promptType(): string {
    return "password";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected formatAnswer(value: string): string {
    if (this.mask) return this.mask.repeat(value.length);
    return "****";
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), mask: this.mask };
  }

  protected async executeTerminal(): Promise<string> {
    const prompt = formatQuestion(this.message);
    return readPassword(prompt, this.mask);
  }
}
