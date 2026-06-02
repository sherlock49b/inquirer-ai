import { ValidationError } from "../errors.js";
import { formatError, formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

// R2 numeric-string grammar: optional sign; required integer part; optional
// .fraction; optional exponent. Accepts "1e3", "3.5", "-2", "1E-3";
// rejects "1_000", "3abc", "0x10", ".5", "5.", "", "+".
const NUMBER_GRAMMAR = /^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/;

export interface NumberConfig extends BaseConfig<number> {
  min?: number | null;
  max?: number | null;
  floatAllowed?: boolean;
  step?: number;
  keepInput?: boolean;
}

export class NumberPrompt extends BasePrompt<number> {
  private min: number | null;
  private max: number | null;
  private floatAllowed: boolean;
  private step: number | null;
  private keepInput: boolean;
  private lastFailedInput: string | null = null;

  constructor(config: NumberConfig) {
    super(config);
    this.min = config.min ?? null;
    this.max = config.max ?? null;
    this.floatAllowed = config.floatAllowed ?? true;
    this.step = config.step ?? null;
    this.keepInput = config.keepInput ?? true;
  }

  get promptType(): string {
    return "number";
  }

  protected validateAnswer(value: unknown): number {
    // R2 numeric-string grammar.
    // 1) null + default present -> default.
    if (value == null && this.defaultValue != null) return this.defaultValue;
    let num: number;
    if (typeof value === "boolean") {
      // booleans are not numbers
      throw new ValidationError(`Expected a number, got boolean`);
    } else if (typeof value === "number") {
      // 2) JSON number (not boolean) -> use it.
      num = value;
    } else if (typeof value === "string") {
      // 3) JSON string: trim leading/trailing ASCII whitespace, then the
      //    remainder MUST fully match the grammar; parse with the native float
      //    parser. Rejects "1_000", "3abc", "0x10", ".5", "5.", "", "+".
      const trimmed = value.replace(/^[\t\n\v\f\r ]+|[\t\n\v\f\r ]+$/g, "");
      if (!NUMBER_GRAMMAR.test(trimmed)) {
        throw new ValidationError(`Not a valid number: ${JSON.stringify(value)}`);
      }
      num = Number.parseFloat(trimmed);
    } else {
      // 4) other type -> "Expected a number, got <type>".
      throw new ValidationError(`Expected a number, got ${typeof value}`);
    }
    // 5) reject non-finite (NaN/Inf).
    if (!Number.isFinite(num)) throw new ValidationError(`Not a valid number: ${JSON.stringify(value)}`);
    if (!this.floatAllowed && num !== Math.trunc(num)) {
      throw new ValidationError("Decimal numbers are not allowed");
    }
    if (!this.floatAllowed) num = Math.trunc(num);
    if (this.min != null && num < this.min) throw new ValidationError(`Must be at least ${this.min}`);
    if (this.max != null && num > this.max) throw new ValidationError(`Must be at most ${this.max}`);
    if (this.step != null) {
      const base = this.min ?? 0;
      const remainder = Math.abs((num - base) % this.step);
      const epsilon = 1e-9;
      if (remainder > epsilon && Math.abs(remainder - this.step) > epsilon) {
        throw new ValidationError(`Must be a multiple of ${this.step} from ${base}`);
      }
    }
    return num;
  }

  protected override toAgentDict(): Record<string, unknown> {
    return {
      ...super.toAgentDict(),
      min: this.min,
      max: this.max,
      float_allowed: this.floatAllowed,
      num_step: this.step,
    };
  }

  protected async executeTerminal(): Promise<number> {
    let currentDefault = this.lastFailedInput ?? (this.defaultValue != null ? String(this.defaultValue) : null);
    while (true) {
      const suffix = currentDefault != null ? ` (${currentDefault})` : "";
      const prompt = formatQuestion(this.message, suffix);
      const raw = await readLine(prompt);
      if (!raw && currentDefault != null) {
        try {
          const result = this.validateAnswer(currentDefault);
          if (this.keepInput) {
            this.lastFailedInput = currentDefault;
          }
          return result;
        } catch (e) {
          if (e instanceof ValidationError) {
            process.stderr.write(`${formatError(e.message)}\n`);
            continue;
          }
          throw e;
        }
      }
      try {
        const result = this.validateAnswer(raw);
        if (this.keepInput && raw) {
          this.lastFailedInput = raw;
        }
        return result;
      } catch (e) {
        if (e instanceof ValidationError) {
          process.stderr.write(`${formatError(e.message)}\n`);
          if (this.keepInput && raw) {
            currentDefault = raw;
            this.lastFailedInput = raw;
          }
          continue;
        }
        throw e;
      }
    }
  }
}
