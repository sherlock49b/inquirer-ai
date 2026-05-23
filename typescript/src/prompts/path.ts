import { formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface PathConfig extends BaseConfig<string> {
  onlyDirectories?: boolean;
}

export class PathPrompt extends BasePrompt<string> {
  private onlyDirectories: boolean;

  constructor(config: PathConfig) {
    super(config);
    this.onlyDirectories = config.onlyDirectories ?? false;
  }

  get promptType(): string {
    return "path";
  }

  protected validateAnswer(value: unknown): string {
    if (value == null) return this.defaultValue ?? "";
    return String(value);
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), only_directories: this.onlyDirectories };
  }

  protected async executeTerminal(): Promise<string> {
    const suffix = this.defaultValue != null ? ` (${this.defaultValue})` : "";
    const prompt = formatQuestion(this.message, suffix);
    const result = await readLine(prompt);
    if (!result && this.defaultValue != null) return this.defaultValue;
    return result;
  }
}
