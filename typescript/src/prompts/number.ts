import { ValidationError } from "../errors.js";
import { formatError, formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface NumberConfig extends BaseConfig<number> {
  min?: number | null;
  max?: number | null;
  floatAllowed?: boolean;
}

export class NumberPrompt extends BasePrompt<number> {
  private min: number | null;
  private max: number | null;
  private floatAllowed: boolean;

  constructor(config: NumberConfig) {
    super(config);
    this.min = config.min ?? null;
    this.max = config.max ?? null;
    this.floatAllowed = config.floatAllowed ?? true;
  }

  get promptType(): string {
    return "number";
  }

  protected validateAnswer(value: unknown): number {
    if (value == null && this.defaultValue != null) return this.defaultValue;
    let num: number;
    if (typeof value === "number" && typeof value !== "boolean") {
      num = value;
    } else if (typeof value === "string") {
      num = value.includes(".") ? parseFloat(value) : parseInt(value, 10);
      if (Number.isNaN(num)) throw new ValidationError(`Not a valid number: ${JSON.stringify(value)}`);
    } else {
      throw new ValidationError(`Expected a number, got ${typeof value}`);
    }
    if (!Number.isFinite(num)) throw new ValidationError(`Not a valid number: ${JSON.stringify(value)}`);
    if (!this.floatAllowed && num !== Math.trunc(num)) {
      throw new ValidationError("Decimal numbers are not allowed");
    }
    if (!this.floatAllowed) num = Math.trunc(num);
    if (this.min != null && num < this.min) throw new ValidationError(`Must be at least ${this.min}`);
    if (this.max != null && num > this.max) throw new ValidationError(`Must be at most ${this.max}`);
    return num;
  }

  protected override toAgentDict(): Record<string, unknown> {
    return {
      ...super.toAgentDict(),
      min: this.min,
      max: this.max,
      float_allowed: this.floatAllowed,
    };
  }

  protected async executeTerminal(): Promise<number> {
    const suffix = this.defaultValue != null ? ` (${this.defaultValue})` : "";
    const prompt = formatQuestion(this.message, suffix);
    while (true) {
      const raw = await readLine(prompt);
      if (!raw && this.defaultValue != null) return this.defaultValue;
      try {
        return this.validateAnswer(raw);
      } catch (e) {
        if (e instanceof ValidationError) {
          process.stderr.write(`${formatError(e.message)}\n`);
          continue;
        }
        throw e;
      }
    }
  }
}
