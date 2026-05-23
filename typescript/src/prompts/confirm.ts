import { formatError, formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface ConfirmConfig extends BaseConfig<boolean> {
  default?: boolean | null;
}

export class ConfirmPrompt extends BasePrompt<boolean> {
  constructor(config: ConfirmConfig) {
    super({ ...config, default: config.default ?? false });
  }

  get promptType(): string {
    return "confirm";
  }

  protected validateAnswer(value: unknown): boolean {
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      return ["y", "yes", "true", "1"].includes(value.toLowerCase());
    }
    return Boolean(value);
  }

  protected formatAnswer(value: boolean): string {
    return value ? "Yes" : "No";
  }

  protected async executeTerminal(): Promise<boolean> {
    const hint = this.defaultValue ? "Y/n" : "y/N";
    const prompt = formatQuestion(this.message, ` (${hint})`);
    while (true) {
      const result = await readLine(prompt);
      if (!result) return this.defaultValue ?? false;
      const lower = result.trim().toLowerCase();
      if (lower === "y" || lower === "yes") return true;
      if (lower === "n" || lower === "no") return false;
      process.stderr.write(`${formatError("Invalid input. Please enter y or n.")}\n`);
    }
  }
}
